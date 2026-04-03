import os
from dotenv import load_dotenv, find_dotenv

# Carrega do ambiente ou env file (procura iterativamente)
env_path = find_dotenv(usecwd=True)
if env_path:
    load_dotenv(env_path)
else:
    load_dotenv()

class Config:
    # R2 / S3
    R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

    # Postgres
    POSTGRES_LOCAL_URI = os.getenv("POSTGRES_LOCAL_URI")

    # Redis / RQ
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_QUEUE = os.getenv("REDIS_QUEUE", "transcription_queue")

    # External APIs
    TRANSCRIBE_URL = os.getenv("TRANSCRIBE_URL", "http://localhost:3000/transcribe")

    @classmethod
    def validate_r2(cls):
        missing = []
        for prop in ["R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
            if not getattr(cls, prop):
                missing.append(prop)
        if missing:
            raise RuntimeError(f"R2 credentials missing. Set: {', '.join(missing)}")
