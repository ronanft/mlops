FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências para o streamlit, worker, banco e filas
RUN pip install --no-cache-dir \
    streamlit \
    rq \
    redis \
    boto3 \
    psycopg2-binary \
    requests \
    python-dotenv

# A pasta do projeto será montada via volume no docker-compose
