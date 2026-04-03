"""Worker de processamento de transcrições.

Implementação baseada nas especificações fornecidas:
- Carrega configuração via config.py e ConnectionManager
- Logging com timestamps e prefixo [WORKER]
- `process_transcription(db_id)` faz download do áudio do R2, envia ao
  serviço de transcrição e atualiza o Postgres
- Consumido via linha de comando padrão `rq worker transcription_queue`
"""

import os
import tempfile
import time
import logging
import threading
from pathlib import Path

import requests

from config import Config
from connections import ConnectionManager
from metrics import (
    start_metrics_server,
    record_transcription_completed,
    record_transcription_failed,
    update_transcriptions_in_progress,
    transcription_duration_seconds
)

# --- Logging ---
logging.basicConfig(
   level=logging.INFO,
   format="%(asctime)s [WORKER] %(levelname)s: %(message)s",
   datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("worker")

# Iniciar servidor de métricas em thread separada
def start_metrics_thread():
    """Inicia o servidor de métricas Prometheus em uma thread separada."""
    try:
        start_metrics_server(port=8002, host='0.0.0.0')
    except Exception as e:
        log.error(f"Failed to start metrics server: {e}")

# Iniciar thread de métricas
metrics_thread = threading.Thread(target=start_metrics_thread, daemon=True)
metrics_thread.start()
log.info("Metrics server thread started on port 8002")

def process_transcription(db_id: str):
   """Processa a transcrição para o registro com id `db_id`."""
   conn = None
   cur = None
   start_time = time.time()
   
   try:
      log.info("Iniciando processamento: %s", db_id)
      # Incrementar contador de transcrições em progresso
      update_transcriptions_in_progress(1)
      conn = ConnectionManager.get_db_connection()
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

      # Atualizar status para PROCESSING
      cur.execute("UPDATE transcriptions SET status = %s WHERE id = %s", ("PROCESSING", db_id))
      conn.commit()

      s3 = ConnectionManager.get_r2_client()
      ext = Path(r2_key).suffix or ""

      # Usando NamedTemporaryFile para garantir limpeza automática no SO
      with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as temp_file:
         log.info("Baixando %s do bucket %s para %s", r2_key, Config.R2_BUCKET_NAME, temp_file.name)
         s3.download_fileobj(Config.R2_BUCKET_NAME, r2_key, temp_file)
         
         # Retorna pointer para inicio, pois o envio envia os bytes lidos
         temp_file.seek(0)

         # Enviar para serviço de transcrição BentoML com retries curtos
         transcribe_url = Config.TRANSCRIBE_URL
         log.info("Enviando arquivo para transcrição: %s", transcribe_url)
         
         max_retries = 3
         timeout = 120 # segundos 
         success = False
         data = {}
         last_exception = None

         for attempt in range(1, max_retries + 1):
             try:
                 temp_file.seek(0) # garante que lê o arquivo novamente se falhar
                 files = {"audio_file": (Path(temp_file.name).name, temp_file)}
                 resp = requests.post(transcribe_url, files=files, timeout=timeout)
                 if resp.status_code == 200:
                    data = resp.json()
                    success = True
                    break
                 else:
                    log.warning(f"Tentativa {attempt} falhou com HTTP {resp.status_code}")
             except requests.exceptions.RequestException as req_e:
                 last_exception = req_e
                 log.warning(f"Tentativa {attempt} falhou ({req_e})")
             
             if attempt < max_retries:
                 time.sleep(5)  # backoff simples
         
         if not success:
             raise RuntimeError(f"Falha na API de transcrição após {max_retries} tentativas. {last_exception}")

         transcription = data.get("transcricao") or data.get("transcription") or ""

      # Fora do contexto de with tempfile, ele já foi removido automaticamente.
      # Atualizar status e salvar resultado
      cur.execute(
         "UPDATE transcriptions SET status = %s, result = %s WHERE id = %s",
         ("COMPLETED", transcription, db_id),
      )
      conn.commit()
      log.info("Processamento concluído para id=%s", db_id)
      
      # Registrar métricas de sucesso
      duration = time.time() - start_time
      transcription_duration_seconds.observe(duration)
      record_transcription_completed()

   except Exception as e:
      log.exception("Erro ao processar id=%s: %s", db_id, e)
      
      # Registrar métricas de falha
      duration = time.time() - start_time
      transcription_duration_seconds.observe(duration)
      error_type = 'api_error' if 'API' in str(e) else 'db_error' if 'database' in str(e).lower() else 'unknown'
      record_transcription_failed(error_type=error_type)
      
      try:
         if conn and cur:
            conn.rollback()
            # Tenta atualizar status para FAILED com a mensagem de erro
            try:
               # Adicione a coluna error_message se existir no banco (mantendo a logica original)
               cur.execute(
                  "UPDATE transcriptions SET status = %s WHERE id = %s",
                  ("FAILED", db_id),
               )
               conn.commit()
            except Exception:
               conn.rollback()
      except Exception:
         log.exception("Erro ao tentar fazer rollback/atualizar status de falha para id=%s", db_id)
  finally:
     # Decrementar contador de transcrições em progresso
     update_transcriptions_in_progress(-1)
     try:
        if cur:
           cur.close()
        if conn:
           conn.close()
     except Exception:
        log.exception("Erro ao fechar conexão com o banco para id=%s", db_id)