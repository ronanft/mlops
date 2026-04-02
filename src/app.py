import streamlit as st
import boto3
import psycopg2
import uuid
import os
from dotenv import load_dotenv
from pathlib import Path
from botocore.config import Config
from redis import Redis
from rq import Queue

# Configuração de caminhos e env
base_path = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=base_path / '.env')

# Configuração do Redis
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_conn = Redis(host=redis_host, port=redis_port)
q = Queue('transcription_queue', connection=redis_conn) # simples assim! e esse será o nome da nossa fila!

# Log: Check queue size at startup
print(f"[DEBUG] Redis connection established. Queue: 'transcription_queue'")
print(f"[DEBUG] Current queue size: {len(q)}")

# Validação de variáveis de ambiente necessárias para R2
required_env = [
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
]
missing = [v for v in required_env if not os.getenv(v)]
if missing:
    raise RuntimeError(f"R2 credentials missing. Set: {', '.join(missing)}")

# Configuração S3 (R2) usando os nomes corretos do .env
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv("R2_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
    region_name="auto"
)

def get_db_connection():
    return psycopg2.connect(os.getenv("POSTGRES_LOCAL_URI"))

def display_transcriptions():
    """Exibe a lista de transcrições na interface."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, filename, status, result, created_at FROM transcriptions ORDER BY created_at DESC LIMIT 10")
                rows = cur.fetchall()
                
                if rows:
                    # Header da tabela
                    col1, col2, col3, col4 = st.columns([1, 3, 2, 4])
                    col1.write("**ID**")
                    col2.write("**Arquivo**")
                    col3.write("**Status**")
                    col4.write("**Resultado**")
                    st.divider()
                    
                    # Linhas da tabela
                    for row in rows:
                        col1, col2, col3, col4 = st.columns([1, 3, 2, 4])
                        col1.write(f"#{row[0]}")
                        col2.write(f"**{row[1]}**")
                        status_color = "🟠" if row[2] == "PENDING" else "🟢"
                        col3.write(f"{status_color} {row[2]}")
                        # Exibir resultado se disponível
                        if row[3]:
                            col4.write(f"{row[3][:100]}{'...' if len(row[3]) > 100 else ''}")
                        else:
                            col4.write("-")
                else:
                    st.info("Nenhuma transcrição encontrada.")
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")

@st.fragment(run_every="10s")
def display_transcriptions_auto():
    """Exibe a lista de transcrições na interface com atualização automática."""
    display_transcriptions()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Whisper MLOps", page_icon="🎙️")

# Inicializar session_state para auto-update
if 'auto_update' not in st.session_state:
    st.session_state.auto_update = False

st.title("🎙️ Transcritor de Áudio Profissional")
st.markdown("Faça o upload do seu áudio para processamento em larga escala.")

uploaded_file = st.file_uploader("Escolha um arquivo (mp3, wav, m4a)", type=["mp3", "wav", "m4a"])

if uploaded_file:
    if st.button("Enviar para Transcrição", use_container_width=True):
        # 1. Gerar Identificadores Únicos
        file_id = str(uuid.uuid4())
        file_extension = uploaded_file.name.split(".")[-1]
        r2_key = f"uploads/{file_id}.{file_extension}"

        try:
            # 2. Upload para Cloudflare R2
            with st.spinner("Subindo arquivo para o R2..."):
                s3_client.upload_fileobj(
                    uploaded_file, 
                    os.getenv("R2_BUCKET_NAME"), 
                    r2_key
                )
            
            # 3. Registrar no Postgres
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO transcriptions (filename, r2_key, status) VALUES (%s, %s, %s) RETURNING id",
                        (uploaded_file.name, r2_key, 'PENDING')
                    )
                    db_id = cur.fetchone()[0]
                    conn.commit()

            st.success(f"✅ Arquivo enviado com sucesso! ID da Transcrição: **{db_id}**")
            st.balloons()

            # Se ok upload para cloudflare e postgres
            job = q.enqueue('worker.process_transcription', args=(db_id,)) # db_id é o id do registro no Postgres
            print(f"[DEBUG] Job enqueued - ID: {job.id}, db_id: {db_id}")
            print(f"[DEBUG] Queue size after enqueue: {len(q)}")
            print(f"[DEBUG] Workers registered: {q.worker_names}")
            st.info(f"Job enviado para a fila do Redis!")
            
        except Exception as e:
            st.error(f"❌ Erro ao processar upload: {e}")

# --- LISTAGEM DE STATUS ---
st.divider()
st.subheader("📋 Status das Transcrições")

# Controles de atualização
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("Atualizar Lista"):
        st.rerun()

with col2:
    st.checkbox("🔄 Atualizações Automáticas", key="auto_update")

with col3:
    # Exibir informações da fila
    queue_size = len(q)
    st.metric("Fila", f"{queue_size} job(s)")

# Botão limpar histórico
if st.button("🗑️ Limpar Histórico", type="secondary"):
        try:
            # Limpar a fila do Redis
            q.empty()
            
            # Limpar todos os registros do PostgreSQL
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transcriptions")
                    conn.commit()
                    
            st.success("✅ Histórico limpo com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao limpar histórico: {e}")

# Exibir a tabela de transcrições
if st.session_state.auto_update:
    display_transcriptions_auto()
else:
    display_transcriptions()