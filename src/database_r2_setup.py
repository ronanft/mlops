import boto3 # pacote de conexão com S3, é o mesmo para R2!
import psycopg2
import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from botocore.config import Config

# Tenta localizar .env subindo hierarquias (mais robusto que path fixo)
env_path = find_dotenv()
if not env_path:
    # Fallback: procura no pai do diretório `src` como antes
    base_path = Path(__file__).resolve().parent.parent
    env_path = str(base_path / '.env')
load_dotenv(env_path)

def init_infra():
    # Configuração do cliente S3 otimizada para Cloudflare R2
    s3 = boto3.client(
        's3',
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version='s3v4'),
        region_name="auto"
    )

    # Verificar bucket específico
    bucket_name = os.getenv("R2_BUCKET_NAME")
    
    if bucket_name:
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"✅ R2 bucket '{bucket_name}' acessível")
        except Exception as e:
            print(f"❌ Erro de conexão com R2: {e}")
            return

    # Conexão com Postgres
    postgres_local_host = os.getenv("POSTGRES_LOCAL_URI")

    try:
        conn = psycopg2.connect(postgres_local_host)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                r2_key TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("✅ Tabela 'transcriptions' criada/verificada no Postgres")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erro ao conectar no Postgres: {e}")
        return

if __name__ == "__main__":
    init_infra()