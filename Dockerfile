FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install mlflow and postgres client once at image build time
RUN pip install --no-cache-dir mlflow[extras] psycopg2-binary

EXPOSE 5000

VOLUME /mlflow
CMD ["sh", "-c", "mlflow server --backend-store-uri ${MLFLOW_BACKEND_STORE_URI} --default-artifact-root ${MLFLOW_DEFAULT_ARTIFACT_ROOT} --serve-artifacts --artifacts-destination /mlflow/artifacts --host 0.0.0.0 --port 5000"]
