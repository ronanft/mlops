"""
Módulo de métricas Prometheus para o aplicativo MLOps.

Este módulo define todas as métricas que serão coletadas pelo Prometheus
para monitoramento do aplicativo de transcrição de áudio.
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import logging

log = logging.getLogger("metrics")

# ==================== CONTADORES ====================

# Contador de transcrições solicitadas
transcription_requests_total = Counter(
    'transcription_requests_total',
    'Total de transcrições solicitadas',
    ['status']  # labels: success, failed, pending
)

# Contador de transcrições completadas
transcription_completed_total = Counter(
    'transcription_completed_total',
    'Total de transcrições completadas com sucesso'
)

# Contador de transcrições falhadas
transcription_failed_total = Counter(
    'transcription_failed_total',
    'Total de transcrições falhadas',
    ['error_type']  # labels: api_error, db_error, etc.
)

# Contador de uploads para R2
upload_requests_total = Counter(
    'upload_requests_total',
    'Total de uploads para R2',
    ['status']  # labels: success, failed
)

# Contador de bytes enviados para R2
upload_bytes_total = Counter(
    'upload_bytes_total',
    'Total de bytes enviados para R2'
)

# ==================== HISTOGRAMAS ====================

# Histograma de tempo de processamento de transcrição
transcription_duration_seconds = Histogram(
    'transcription_duration_seconds',
    'Tempo de processamento de transcrição em segundos',
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

# ==================== GAUGES ====================

# Gauge de tamanho da fila RQ
queue_size = Gauge(
    'queue_size',
    'Tamanho atual da fila RQ de transcrições'
)

# Gauge de jobs ativos no worker
active_jobs = Gauge(
    'active_jobs',
    'Número de jobs ativos no worker'
)

# Gauge de transcrições em processamento
transcriptions_in_progress = Gauge(
    'transcriptions_in_progress',
    'Número de transcrições atualmente em processamento'
)


# ==================== FUNÇÕES AUXILIARES ====================

def start_metrics_server(port: int = 8000, host: str = '0.0.0.0'):
    """
    Inicia o servidor HTTP do Prometheus para expor as métricas.

    Args:
        port: Porta onde o servidor irá escutar (padrão: 8000)
        host: Host onde o servidor irá escutar (padrão: 0.0.0.0)
    """
    try:
        start_http_server(port, host)
        log.info(f"Servidor de métricas Prometheus iniciado em {host}:{port}")
    except Exception as e:
        log.error(f"Erro ao iniciar servidor de métricas: {e}")
        raise


def record_transcription_request(status: str = 'pending'):
    """
    Registra uma nova solicitação de transcrição.

    Args:
        status: Status da transcrição (success, failed, pending)
    """
    transcription_requests_total.labels(status=status).inc()


def record_transcription_completed():
    """Registra uma transcrição completada com sucesso."""
    transcription_completed_total.inc()


def record_transcription_failed(error_type: str = 'unknown'):
    """
    Registra uma transcrição falhada.

    Args:
        error_type: Tipo de erro (api_error, db_error, etc.)
    """
    transcription_failed_total.labels(error_type=error_type).inc()


def record_upload(status: str = 'success', bytes_sent: int = 0):
    """
    Registra um upload para R2.

    Args:
        status: Status do upload (success, failed)
        bytes_sent: Número de bytes enviados
    """
    upload_requests_total.labels(status=status).inc()
    if bytes_sent > 0:
        upload_bytes_total.inc(bytes_sent)


def update_queue_size(size: int):
    """
    Atualiza o gauge de tamanho da fila.

    Args:
        size: Tamanho atual da fila
    """
    queue_size.set(size)


def update_active_jobs(count: int):
    """
    Atualiza o gauge de jobs ativos.

    Args:
        count: Número de jobs ativos
    """
    active_jobs.set(count)


def update_transcriptions_in_progress(count: int):
    """
    Atualiza o gauge de transcrições em processamento.

    Args:
        count: Número de transcrições em processamento
    """
    transcriptions_in_progress.set(count)
