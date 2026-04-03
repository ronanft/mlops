# Observabilidade e CI/CD

Este documento descreve como configurar e usar os recursos de observabilidade e CI/CD do projeto.

## Observabilidade

### Acessando o Grafana

O Grafana está configurado para rodar na porta **3030** (para evitar conflito com BentoML que usa a porta 3000).

- **URL**: `http://localhost:3030`
- **Usuário**: `admin`
- **Senha**: `admin` (alterar no primeiro acesso)

### Dashboards Disponíveis

Existem três dashboards pré-configurados:

1. **System Metrics** (`system-metrics`)
   - CPU Usage
   - Memory Usage
   - Network I/O
   - Disk I/O
   - Node Exporter Status
   - Prometheus Status

2. **Application Metrics** (`application-metrics`)
   - Transcription Requests Rate
   - Transcription Total Count
   - Transcription Duration (Percentiles)
   - Queue Size
   - Active Transcriptions
   - Upload Rate to R2
   - Error Rate
   - Streamlit App Status

3. **Overview Dashboard** (`overview-dashboard`)
   - Visão geral de todas as métricas
   - Status dos serviços
   - Recursos do sistema
   - Métricas do aplicativo

### Adicionando Novos Dashboards

Para adicionar um novo dashboard ao Grafana:

1. Acesse `http://localhost:3030`
2. Clique em **Dashboards** → **Import**
3. Cole o JSON do dashboard ou use o ID do Grafana.com
4. Clique em **Load** e depois em **Import**

### Métricas Disponíveis

#### Métricas do Aplicativo

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `transcription_requests_total` | Counter | Total de transcrições solicitadas |
| `transcription_completed_total` | Counter | Total de transcrições completadas |
| `transcription_failed_total` | Counter | Total de transcrições falhadas |
| `transcription_duration_seconds` | Histogram | Tempo de processamento de transcrição |
| `queue_size` | Gauge | Tamanho atual da fila RQ |
| `active_jobs` | Gauge | Número de jobs ativos no worker |
| `upload_requests_total` | Counter | Total de uploads para R2 |
| `upload_bytes_total` | Counter | Total de bytes enviados para R2 |

#### Métricas do Sistema (Node Exporter)

| Métrica | Descrição |
|---------|-----------|
| `node_cpu_seconds_total` | Tempo de CPU por modo |
| `node_memory_MemAvailable_bytes` | Memória disponível |
| `node_memory_MemTotal_bytes` | Memória total |
| `node_network_receive_bytes_total` | Bytes recebidos pela rede |
| `node_network_transmit_bytes_total` | Bytes transmitidos pela rede |
| `node_disk_io_time_seconds_total` | Tempo de I/O do disco |

## CI/CD com GitHub Actions

### Configurando Secrets do GitHub

Para usar o workflow de CI/CD, você precisa configurar os seguintes secrets no seu repositório GitHub:

1. Vá para **Settings** → **Secrets and variables** → **Actions**
2. Clique em **New repository secret**
3. Adicione os seguintes secrets:

| Secret | Descrição | Exemplo |
|--------|-----------|---------|
| `GCP_SA_KEY` | Service Account key em base64 | `eyJhbGciOi...` |
| `PROJECT_ID` | ID do projeto GCP | `my-mlops-project` |
| `REGION` | Região do Artifact Registry | `us-central1` |
| `REPOSITORY` | Nome do repositório | `mlops-repo` |

### Configurando Service Account no GCP

1. **Criar Service Account**:
   ```bash
   gcloud iam service-accounts create mlops-ci-cd \
     --display-name="MLOps CI/CD" \
     --project=${PROJECT_ID}
   ```

2. **Conceder permissões**:
   ```bash
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:mlops-ci-cd@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/artifactregistry.writer"
   ```

3. **Criar chave JSON**:
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account=mlops-ci-cd@${PROJECT_ID}.iam.gserviceaccount.com
   ```

4. **Converter para base64**:
   ```bash
   cat key.json | base64 -w 0
   ```

5. **Adicionar como secret** no GitHub (veja acima)

### Criando Artifact Registry

Se você ainda não tem um Artifact Registry:

```bash
gcloud artifacts repositories create ${REPOSITORY} \
  --repository-format=docker \
  --location=${REGION} \
  --project=${PROJECT_ID}
```

### Workflow de CI/CD

O workflow `.github/workflows/docker-build-push.yml` é acionado automaticamente:

- **Push para branch `main`**: Build e push da imagem com tags `latest` e `main-{sha}`
- **Tags no formato `v*`**: Build e push da imagem com tags de versão (ex: `v1.0.0`, `v1.0`)
- **Pull Requests**: Build apenas (sem push) para testes

### Imagens Docker

O workflow builda apenas a imagem `app` (usando `Dockerfile.app`):

- **Registry**: `${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/app`
- **Tags**:
  - `latest` (apenas no branch main)
  - `main-{git-sha}` (apenas no branch main)
  - `v{version}` (apenas em tags de release)
  - `{git-sha}` (sempre)

### Usando a Imagem do Registry

Para usar a imagem do Artifact Registry no `docker-compose.yml`, atualize o serviço `streamlit` e `rq_worker`:

```yaml
streamlit:
  image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/app:latest
  # ... resto da configuração

rq_worker:
  image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/app:latest
  # ... resto da configuração
```

Ou use uma versão específica:

```yaml
streamlit:
  image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/app:v1.0.0
  # ... resto da configuração
```

## Iniciando os Serviços

### Com Docker Compose

```bash
# Iniciar todos os serviços (incluindo monitoramento)
docker-compose up -d

# Verificar status dos serviços
docker-compose ps

# Ver logs de um serviço específico
docker-compose logs -f grafana
docker-compose logs -f prometheus
```

### Serviços Disponíveis

| Serviço | Porta | Descrição |
|---------|--------|-----------|
| Streamlit | 8501 | Interface web do aplicativo |
| MLflow | 5000 | Servidor de tracking MLflow |
| PostgreSQL | 5432 | Banco de dados |
| Redis | 6379 | Fila de tarefas |
| Prometheus | 9090 | Coletor de métricas |
| Grafana | 3030 | Visualização de métricas |
| Node Exporter | 9100 | Métricas do sistema |

## Troubleshooting

### Grafana não consegue conectar ao Prometheus

1. Verifique se o Prometheus está rodando:
   ```bash
   docker-compose ps prometheus
   ```

2. Verifique os logs do Prometheus:
   ```bash
   docker-compose logs prometheus
   ```

3. Verifique a configuração do datasource no Grafana:
   - Settings → Data Sources → Prometheus
   - URL deve ser `http://prometheus:9090`

### Métricas do aplicativo não aparecem

1. Verifique se os servidores de métricas estão rodando:
   ```bash
   # Ver logs do streamlit
   docker-compose logs streamlit | grep metrics
   
   # Ver logs do worker
   docker-compose logs rq_worker | grep metrics
   ```

2. Verifique se as portas estão expostas:
   - Streamlit: `streamlit:8001`
   - Worker: `rq_worker:8002`

3. Verifique a configuração do Prometheus:
   ```bash
   # Ver targets
   curl http://localhost:9090/api/v1/targets
   ```

### CI/CD falha com erro de autenticação

1. Verifique se os secrets estão configurados corretamente no GitHub
2. Verifique se a Service Account tem as permissões corretas
3. Verifique se o Artifact Registry existe

### Imagem não é pushada

1. Verifique se o Artifact Registry existe
2. Verifique se a Service Account tem permissão de escrita
3. Verifique os logs do workflow no GitHub Actions

## Recursos Adicionais

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Google Cloud Artifact Registry](https://cloud.google.com/artifact-registry)
