#!/bin/bash

# Nome do container e da rede
CONTAINER_NAME="whisper-service"
NETWORK_NAME="mlops_ml_net"
IMAGE_NAME="whisper_transcriber:3oem66rpnooazgk6"

# 1. Cria a rede se ela não existir
docker network inspect $NETWORK_NAME >/dev/null 2>&1 || \
    docker network create $NETWORK_NAME

# 2. Para e remove o container se ele já estiver rodando (evita erro de nome em uso)
echo "Limpando containers antigos..."
docker stop $CONTAINER_NAME >/dev/null 2>&1
docker rm $CONTAINER_NAME >/dev/null 2>&1

# 3. Roda o container
# --name: Define o nome fixo para o DNS interno
# --network: Conecta à rede do worker
# --gpus all: Garante acesso à GPU
echo "Iniciando o serviço Whisper em http://$CONTAINER_NAME:3000"

docker run -d \
  --name $CONTAINER_NAME \
  --network $NETWORK_NAME \
  --gpus all \
  -p 3000:3000 \
  --rm \
  $IMAGE_NAME

echo "Aguardando o serviço estabilizar..."
