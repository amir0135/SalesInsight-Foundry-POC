# Local Development Guide

Detailed setup options, configuration, and troubleshooting for developing locally.

> **First time?** Start with [Getting Started](../GETTING_STARTED.md) to deploy Azure resources and get running quickly. Come back here for Docker, manual config, or troubleshooting.

---

## Prerequisites

- [Python 3.11+](https://www.python.org)
- [Node.js 20+](https://nodejs.org)
- [Poetry](https://python-poetry.org/docs/#installation)
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (for local PostgreSQL or Docker-based setup)
- Azure Functions Core Tools: `npm install -g azure-functions-core-tools@4`
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli) + [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)

Or install everything at once:

```bash
./scripts/install_prerequisites.sh
```

---

## Configuration

### Option A: Pull from Azure (recommended)

If you've already run `azd up`, this creates your `.env` automatically:

```bash
./scripts/setup_local.sh
```

### Option B: Manual configuration

```bash
cp .env.example .env
```

Edit `.env` — at minimum fill in:
- `AZURE_OPENAI_RESOURCE`, `AZURE_OPENAI_MODEL`, `AZURE_OPENAI_API_KEY`
- `AZURE_SEARCH_SERVICE`, `AZURE_SEARCH_INDEX`, `AZURE_SEARCH_KEY`
- `AZURE_BLOB_ACCOUNT_NAME`, `AZURE_BLOB_ACCOUNT_KEY`

See [.env.example](../.env.example) for all available settings with descriptions.

---

## Running the App

### Standard (recommended for development)

```bash
poetry install
cd code/frontend && npm install && cd ../..
./start_local.sh
```

### Docker (no local Python/Node required)

```bash
cp .env.example .env
# Edit .env with your credentials

docker-compose -f docker/docker-compose.local.yml up --build
```

> Docker serves the Chat UI on port **8080** instead of 5173.

---

## Services

| Service | URL | Technology |
|---------|-----|------------|
| Chat UI | http://localhost:5173 (dev) / http://localhost:8080 (Docker) | React + Vite |
| Chat API | http://localhost:5050 | Flask |
| Admin UI | http://localhost:8501 | Streamlit |
| Azure Functions | http://localhost:7071 | Azure Functions Core Tools |
| PostgreSQL | localhost:5432 | Docker container (chat history) |

To stop all services:

```bash
./stop_local.sh
```

---

## Troubleshooting

### Flask won't start
```bash
tail -f /tmp/flask.log
# Common fix: ensure .venv is activated
source .venv/bin/activate
```

### Azure Functions won't start
```bash
tail -f /tmp/functions.log
# Install Azure Functions Core Tools if missing:
npm install -g azure-functions-core-tools@4
```

### Document processing fails
```bash
# Ensure you have the required Azure RBAC roles:
# - Storage Blob Data Contributor
# - Storage Queue Data Contributor
# - Search Index Data Contributor
# Run setup script to auto-configure:
./scripts/setup_local.sh
```

### PostgreSQL container issues
```bash
docker stop database-postgres && docker rm database-postgres
# Restart — start_local.sh will recreate it:
./start_local.sh
```

### Port already in use
```bash
./stop_local.sh    # Kill leftover processes, then restart
```

---

## Azure Resources Created by `azd up`

| Resource | Purpose |
|----------|---------|
| Azure OpenAI | GPT-4o + embedding models |
| Azure AI Search | Document indexing and vector search |
| Azure Blob Storage | Document staging and configuration |
| Azure Cosmos DB | Conversation history (default) |
| Azure App Service (x3) | Web, Admin, and Functions hosting |
| Azure Key Vault | Secrets management |
| Azure Document Intelligence | PDF and document parsing |
