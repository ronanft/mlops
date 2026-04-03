import streamlit as st
import uuid
import os
import threading
import time
from connections import ConnectionManager
from config import Config
from metrics import (
    start_metrics_server,
    record_transcription_request,
    record_upload,
    update_queue_size
)

# Recuperar as dependências globais via ConnectionManager
q = ConnectionManager.get_rq_queue()
s3_client = ConnectionManager.get_r2_client()

# Log: Check queue size at startup
print(f"[DEBUG] Redis/RQ connection established. Queue: '{Config.REDIS_QUEUE}'")
print(f"[DEBUG] Current queue size: {len(q)}")

# Iniciar servidor de métricas em thread separada
def start_metrics_thread():
    """Inicia o servidor de métricas Prometheus em uma thread separada."""
    try:
        start_metrics_server(port=8001, host='0.0.0.0')
    except Exception as e:
        print(f"[ERROR] Failed to start metrics server: {e}")

# Iniciar thread de métricas
metrics_thread = threading.Thread(target=start_metrics_thread, daemon=True)
metrics_thread.start()
print("[DEBUG] Metrics server thread started on port 8001")

# Função para atualizar periodicamente o gauge de tamanho da fila
def update_queue_metrics():
    """Atualiza periodicamente o gauge de tamanho da fila."""
    while True:
        try:
            queue_size = len(q)
            update_queue_size(queue_size)
        except Exception as e:
            print(f"[ERROR] Failed to update queue metrics: {e}")
        time.sleep(10)  # Atualiza a cada 10 segundos

# Iniciar thread de atualização de métricas
queue_metrics_thread = threading.Thread(target=update_queue_metrics, daemon=True)
queue_metrics_thread.start()
print("[DEBUG] Queue metrics update thread started")

def get_db_connection():
    return ConnectionManager.get_db_connection()

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
                file_size = len(uploaded_file.read())
                uploaded_file.seek(0)  # Resetar o ponteiro do arquivo
                s3_client.upload_fileobj(
                    uploaded_file,
                    os.getenv("R2_BUCKET_NAME"),
                    r2_key
                )
                # Registrar métrica de upload
                record_upload(status='success', bytes_sent=file_size)
            
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
            # Enqueue usando o caminho de módulo completo para evitar erro
            # "Invalid attribute name: worker.process_transcription" quando
            # o worker não encontra o módulo no PYTHONPATH.
            from worker import process_transcription
            job = q.enqueue(process_transcription, args=(str(db_id),))
            print(f"[DEBUG] Job enqueued - ID: {job.id}, db_id: {db_id}")
            print(f"[DEBUG] Queue size after enqueue: {len(q)}")
            st.info(f"Job enviado para a fila do Redis!")
            
            # Registrar métrica de transcrição solicitada
            record_transcription_request(status='pending')
            
        except Exception as e:
            st.error(f"❌ Erro ao processar upload: {e}")
            # Registrar métrica de upload falhado
            record_upload(status='failed', bytes_sent=0)

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