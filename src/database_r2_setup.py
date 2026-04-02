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
    print(f"🔍 Carregando configurações de: {env_path}")
    
    # 2. Configuração do cliente S3 otimizada para Cloudflare R2
    # O R2 exige signature_version='s3v4' em alguns SDKs e o parâmetro region_name='auto'
    s3 = boto3.client(
        's3',
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version='s3v4'),
        region_name="auto"
    )

    try:
        # Testa a conexão listando os buckets
        response = s3.list_buckets()
        print("✅ Conexão com Cloudflare R2: OK")
                    
    except Exception as e:
        print(f"❌ Erro de conexão com R2: {e}")
        return # Interrompe se o R2 falhar

    # 3. Conexão com Postgres usando a string de conexão do .env (POSTGRES_URI)
    try:
        # Dica: Verifique se o DB_CONFIG no .env está entre aspas se contiver caracteres especiais
        conn = psycopg2.connect(os.getenv("POSTGRES_URI"))
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
        print("✅ Tabela 'transcriptions' verificada/criada no Postgres.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erro no Postgres: {e}")

if __name__ == "__main__":
    init_infra()