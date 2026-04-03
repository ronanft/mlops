# MLOps - Transcritor de Áudio com Observabilidade e CI/CD

Projeto MLOps de exemplo para demonstração de observabilidade com Grafana/Prometheus e CI/CD com GitHub Actions.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Configuração](#configuração)
- [Executando o Projeto](#executando-o-projeto)
- [Observabilidade](#observabilidade)
- [CI/CD](#cicd)
- [Documentação](#documentação)

## Visão Geral

Este projeto consiste em um sistema de transcrição de áudio usando Whisper, com as seguintes características:

- **Interface Web**: Streamlit para upload e acompanhamento de transcrições
- **Processamento**: RQ Workers para processamento assíncrono
- **Armazenamento**: Cloudflare R2 para arquivos de áudio
- **Banco de Dados**: PostgreSQL para metadados
- **Fila**: Redis para gerenciamento de tarefas
- **Tracking**: MLflow para experimentos de ML
- **Observabilidade**: Prometheus + Grafana para monitoramento
- **CI/CD**: GitHub Actions para build e push de imagens Docker

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose                          │
├─────────────────────────────────────────────────────────────────────┤
│  Aplicação                                                      │
│  ├── Streamlit (Porta 8501)                                   │
│  ├── RQ Worker                                                   │
│  ├── MLflow Server (Porta 5000)                                │
│  ├── PostgreSQL (Porta 5432)                                   │
│  └── Redis (Porta 6379)                                        │
├─────────────────────────────────────────────────────────────────────┤
│  Monitoramento                                                   │
│  ├── Prometheus (Porta 9090)                                    │
│  ├── Grafana (Porta 3030)                                       │
│  └── Node Exporter (Porta 9100)                                │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  GitHub Actions │
                    │   CI/CD        │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ GCP Artifact    │
                    │   Registry      │
                    └─────────────────┘
```

## Pré-requisitos

- Docker e Docker Compose
- Python 3.11+
- Conta Google Cloud (para CI/CD)
- Conta GitHub (para CI/CD)

## Configuração

### 1. Variáveis de Ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:

```env
# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000
POSTGRES_URI=postgresql://user:password@localhost:5432/mlops
MLFLOW_BACKEND_STORE_URI=postgresql://user:password@localhost:5432/mlops
MLFLOW_DEFAULT_ARTIFACT_ROOT=mlflow-artifacts:/mlflow

# PostgreSQL
POSTGRES_USER=mlops_user
POSTGRES_PASSWORD=mlops_password
POSTGRES_DB=mlops

# Redis
REDIS_PORT=6379

# Cloudflare R2
R2_BUCKET_NAME=your-bucket-name
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key

# Transcrição
TRANSCRIBE_URL=http://localhost:3000/transcribe
```

### 2. Configuração do CI/CD

Para usar o CI/CD, configure os secrets no GitHub:

- `GCP_SA_KEY`: Service Account key em base64
- `PROJECT_ID`: ID do projeto GCP
- `REGION`: Região do Artifact Registry (ex: `us-central1`)
- `REPOSITORY`: Nome do repositório (ex: `mlops-repo`)

Veja [docs/observabilidade-cicd.md](docs/observabilidade-cicd.md) para instruções detalhadas.

## Executando o Projeto

### Iniciar todos os serviços:

```bash
docker-compose up -d
```

### Verificar status dos serviços:

```bash
docker-compose ps
```

### Ver logs de um serviço:

```bash
docker-compose logs -f streamlit
docker-compose logs -f grafana
```

### Parar todos os serviços:

```bash
docker-compose down
```

## Observabilidade

### Acessando o Grafana

- **URL**: http://localhost:3030
- **Usuário**: `admin`
- **Senha**: `admin` (alterar no primeiro acesso)

### Dashboards Disponíveis

1. **System Metrics**: CPU, memória, rede, disco
2. **Application Metrics**: Transcrições, fila, erros
3. **Overview Dashboard**: Visão geral combinada

### Métricas do Aplicativo

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `transcription_requests_total` | Counter | Total de transcrições solicitadas |
| `transcription_completed_total` | Counter | Total de transcrições completadas |
| `transcription_failed_total` | Counter | Total de transcrições falhadas |
| `transcription_duration_seconds` | Histogram | Tempo de processamento |
| `queue_size` | Gauge | Tamanho da fila RQ |
| `active_jobs` | Gauge | Jobs ativos no worker |
| `upload_requests_total` | Counter | Uploads para R2 |
| `upload_bytes_total` | Counter | Bytes enviados para R2 |

Veja [docs/observabilidade-cicd.md](docs/observabilidade-cicd.md) para mais detalhes.

## CI/CD

O workflow `.github/workflows/docker-build-push.yml` automatiza o build e push de imagens Docker.

### Triggers

- **Push para `main`**: Build e push com tags `latest` e `main-{sha}`
- **Tags `v*`**: Build e push com tags de versão (ex: `v1.0.0`)
- **Pull Requests**: Build apenas (sem push) para testes

### Imagem Docker

- **Registry**: `${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/app`
- **Dockerfile**: `Dockerfile.app`

Veja [docs/observabilidade-cicd.md](docs/observabilidade-cicd.md) para instruções detalhadas.

## Documentação

- [Observabilidade e CI/CD](docs/observabilidade-cicd.md) - Documentação completa de observabilidade e CI/CD
- [Plano de Implementação](plans/observabilidade-cicd.md) - Plano detalhado da implementação

## Estrutura do Projeto

```
.
├── .github/
│   └── workflows/
│       └── docker-build-push.yml    # Workflow de CI/CD
├── docs/
│   └── observabilidade-cicd.md      # Documentação
├── grafana/
│   ├── dashboards/
│   │   ├── system.json              # Dashboard de sistema
│   │   ├── application.json         # Dashboard de aplicativo
│   │   └── overview.json            # Dashboard combinado
│   └── provisioning/
│       └── datasources/
│           └── prometheus.yml       # Config datasource
├── plans/
│   └── observabilidade-cicd.md      # Plano de implementação
├── prometheus/
│   └── prometheus.yml               # Config Prometheus
├── src/
│   ├── app.py                      # Interface Streamlit
│   ├── worker.py                   # RQ Worker
│   ├── metrics.py                  # Métricas Prometheus
│   ├── config.py                   # Configurações
│   ├── connections.py              # Conexões DB/R2/Redis
│   └── service.py                  # Serviço BentoML
├── docker-compose.yml                # Orquestração
├── Dockerfile                      # Imagem MLflow
├── Dockerfile.app                  # Imagem App
└── README.md                       # Este arquivo
```

## Licença

Este é um projeto de exemplo educacional.
