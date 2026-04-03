import boto3
import psycopg2
from redis import Redis
from rq import Queue
from botocore.config import Config as BotoConfig
from config import Config

class ConnectionManager:
    _r2_client = None
    _postgres_conn = None
    _redis_conn = None
    _rq_queue = None

    @classmethod
    def get_r2_client(cls):
        if cls._r2_client is None:
            Config.validate_r2()
            cls._r2_client = boto3.client(
                's3',
                endpoint_url=Config.R2_ENDPOINT_URL,
                aws_access_key_id=Config.R2_ACCESS_KEY_ID,
                aws_secret_access_key=Config.R2_SECRET_ACCESS_KEY,
                config=BotoConfig(signature_version='s3v4', s3={'addressing_style': 'path'}),
                region_name="auto"
            )
        return cls._r2_client

    @classmethod
    def get_db_connection(cls):
        # Sempre retorna uma nova conexão, pois sem pooling, conexões fechadas dariam erro
        if not Config.POSTGRES_LOCAL_URI:
            raise RuntimeError("POSTGRES_LOCAL_URI não definida")
        return psycopg2.connect(Config.POSTGRES_LOCAL_URI)

    @classmethod
    def get_redis_conn(cls):
        if cls._redis_conn is None:
            cls._redis_conn = Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)
        return cls._redis_conn

    @classmethod
    def get_rq_queue(cls):
        if cls._rq_queue is None:
            cls._rq_queue = Queue(Config.REDIS_QUEUE, connection=cls.get_redis_conn())
        return cls._rq_queue
