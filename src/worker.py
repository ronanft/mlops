"""Worker de processamento de transcrições.

Implementação baseada nas especificações fornecidas:
- Carrega variáveis de ambiente via python-dotenv
- Logging com timestamps e prefixo [WORKER]
- `process_transcription(db_id)` faz download do áudio do R2, envia ao
  serviço de transcrição e atualiza o Postgres
- Loop principal consome IDs de uma fila Redis e chama `process_transcription`
"""

import os
import tempfile
import time
import logging
from pathlib import Path

import boto3
from botocore.config import Config
import psycopg2
import requests
import redis

# imports listados nas especificações (podem permanecer não usados diretamente)
# import torch
from transformers import pipeline

from dotenv import load_dotenv, find_dotenv


# --- Configuração de ambiente ---
env_path = find_dotenv(usecwd=True)
if env_path:
   load_dotenv(env_path)
else:
   load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_LOCAL_URI")
R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
R2_BUCKET = os.getenv("R2_BUCKET_NAME") 
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "transcription_queue")


# --- Logging ---
logging.basicConfig(
   level=logging.INFO,
   format="%(asctime)s [WORKER] %(levelname)s: %(message)s",
   datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("worker")


def get_db_connection():
   if not DATABASE_URL:
      raise RuntimeError("DATABASE_URL não definida")
   return psycopg2.connect(DATABASE_URL)


def get_r2_client():
   if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
      raise RuntimeError("Configuração R2 incompleta (R2_ENDPOINT/R2_ACCESS_KEY/R2_SECRET_KEY)")
   cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"})
   client = boto3.client(
      "s3",
      endpoint_url=R2_ENDPOINT,
      aws_access_key_id=R2_ACCESS_KEY,
      aws_secret_access_key=R2_SECRET_KEY,
      region_name="auto",
      config=cfg,
   )
   return client


def process_transcription(db_id: str):
   """Processa a transcrição para o registro com id `db_id`.

   O fluxo é:
   - buscar r2_key no Postgres
   - atualizar status para PROCESSING
   - baixar arquivo do R2 para arquivo temporário
   - enviar para serviço de transcrição BentoML
   - atualizar status e salvar resultado
   - limpar arquivo temporário
   """
   conn = None
   cur = None
   temp_path = None
   try:
      log.info("Iniciando processamento: %s", db_id)
      conn = get_db_connection()
      conn.autocommit = False
      cur = conn.cursor()

      # Buscar metadados (r2_key)
      cur.execute("SELECT r2_key FROM transcriptions WHERE id = %s", (db_id,))
      row = cur.fetchone()
      if not row:
         log.error("Registro não encontrado no banco para id=%s", db_id)
         return
      r2_key = row[0]
      log.info("r2_key encontrado: %s", r2_key)

      # Extrair extensão do arquivo
      ext = Path(r2_key).suffix or ""

      # Atualizar status para PROCESSING
      cur.execute("UPDATE transcriptions SET status = %s WHERE id = %s", ("PROCESSING", db_id))
      conn.commit()

      # Preparar cliente R2 e arquivo temporário
      s3 = get_r2_client()
      tmp_dir = Path(tempfile.gettempdir())
      temp_path = tmp_dir / f"temp_{db_id}{ext}"

      log.info("Baixando %s do bucket %s para %s", r2_key, R2_BUCKET, temp_path)
      s3.download_file(R2_BUCKET, r2_key, str(temp_path))

      # Enviar para serviço de transcrição BentoML
      transcribe_url = os.getenv("TRANSCRIBE_URL", "http://localhost:3000/transcribe")
      with open(temp_path, "rb") as fh:
         files = {"audio_file": (temp_path.name, fh)}
         log.info("Enviando arquivo para transcrição: %s", transcribe_url)
         resp = requests.post(transcribe_url, files=files, timeout=800)
      resp.raise_for_status()
      data = resp.json()
      transcription = data.get("transcricao") or data.get("transcription") or ""

      # Atualizar status e salvar resultado
      cur.execute(
         "UPDATE transcriptions SET status = %s, result = %s WHERE id = %s",
         ("COMPLETED", transcription, db_id),
      )
      conn.commit()
      log.info("Processamento concluído para id=%s", db_id)

   except Exception as e:
      log.exception("Erro ao processar id=%s: %s", db_id, e)
      try:
         if conn and cur:
            conn.rollback()
            # Tenta atualizar status para FAILED com a mensagem de erro
            try:
               cur.execute(
                  "UPDATE transcriptions SET status = %s, error_message = %s WHERE id = %s",
                  ("FAILED", str(e), db_id),
               )
               conn.commit()
            except Exception:
               conn.rollback()
      except Exception:
         log.exception("Erro ao tentar fazer rollback/atualizar status de falha para id=%s", db_id)
   finally:
      # Fechar cursor/conn e remover arquivo temporário
      try:
         if cur:
            cur.close()
         if conn:
            conn.close()
      except Exception:
         log.exception("Erro ao fechar conexão com o banco para id=%s", db_id)
      if temp_path and temp_path.exists():
         try:
            temp_path.unlink()
            log.info("Arquivo temporário removido: %s", temp_path)
         except Exception:
            log.exception("Falha ao remover arquivo temporário: %s", temp_path)


def worker_loop():
   r = redis.from_url(REDIS_URL)
   log.info("Worker iniciado. Escutando fila Redis: %s", REDIS_QUEUE)
   while True:
      try:
         item = r.brpop(REDIS_QUEUE, timeout=5)
         if not item:
            # Nada na fila, pausa curta
            time.sleep(1)
            continue

         # brpop normalmente retorna uma tupla (queue, value).
         # Seja robusto: trate lista/tupla ou valor direto.
         if isinstance(item, (list, tuple)) and len(item) >= 2:
            raw = item[1]
         else:
            raw = item

         db_id = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
         process_transcription(db_id)
      except Exception as e:
         log.exception("Erro no loop do worker: %s", e)
         time.sleep(10)


if __name__ == "__main__":
   try:
      worker_loop()
   except KeyboardInterrupt:
      log.info("Worker finalizado por interrupção do usuário")