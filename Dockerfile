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

CMD ["mlflow", "server", "--backend-store-uri", "postgresql://postgres:megapassword@postgres:5432/mlflowdb", "--default-artifact-root", "mlflow-artifacts:/", "--serve-artifacts", "--artifacts-destination", "/mlflow/artifacts", "--host", "0.0.0.0", "--port", "5000"]
