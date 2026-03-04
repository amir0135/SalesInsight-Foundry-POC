# Copilot Instructions for SalesInsight Foundry POC

## What This Project Does

This is a **Sales Insight RAG (Retrieval-Augmented Generation) POC** built on the Azure OpenAI "Chat With Your Data" accelerator. It allows users to query sales order history data (order lines, delivery dates, pricing, status) using natural language.

**Primary data source:** `data/db_more_weu_prod_dbo_OrderHistoryLine.csv` — contains order history with columns: Id, OrderType, RequestedDeliveryDate, ConfirmedDeliveryDate, RequestQuantity, UnitNetPrice, StyleNumber, Status, BrandId, ProductLineId, etc.

## Quick Start (Local Development)

```bash
# 1. Copy environment config
cp .env.example .env
# Edit .env — fill in AZURE_OPENAI_*, AZURE_SEARCH_*, AZURE_BLOB_*

# 2. Start all services
./start_local.sh

# 3. Open the apps
#    Chat UI:  http://localhost:5173
#    Admin UI: http://localhost:8501
```

### How to Load the Sales CSV Data

1. Open Admin UI at `http://localhost:8501`
2. Go to **"01 Ingest Data"**
3. Upload `data/db_more_weu_prod_dbo_OrderHistoryLine.csv` (CSV is now a supported type)
4. Wait for Azure Functions to process and index it (async — check function logs)
5. Open Chat UI and ask questions like:
   - "What orders are in OPEN status?"
   - "Show me orders for brand B_21 with delivery after April 2026"
   - "What is the total net value of ALLOCATED orders?"

### Deploy to Azure

```bash
azd deploy web        # Deploy chat UI only (fastest — ~2 min)
azd deploy adminweb   # Deploy admin UI only
azd deploy function   # Deploy Azure Functions only
azd up                # Deploy everything (slower — ~10 min, use sparingly)
```

**Tip:** Use `azd deploy <service>` for individual service updates instead of `azd up` to avoid full re-provisioning.

## Architecture Overview

| Service | Path | Technology | Purpose |
|---------|------|------------|---------|
| **web** | `code/` | Flask | Main chat API serving the React frontend |
| **adminweb** | `code/backend/` | Streamlit | Document ingestion/configuration UI |
| **function** | `code/backend/batch/` | Azure Functions | Background processing (embeddings, batch indexing) |

### Key Data Flow
1. CSV/documents uploaded via Admin UI (`01_Ingest_Data.py`) → stored in Azure Blob Storage
2. Azure Functions process documents → chunk → embed via Azure OpenAI → index in Azure AI Search
3. Chat queries hit Flask API → orchestrator retrieves context from search → LLM generates response

## Critical Configuration Patterns

### Environment Variables (`EnvHelper`)
All configuration loads through the singleton `EnvHelper` class at [code/backend/batch/utilities/helpers/env_helper.py](code/backend/batch/utilities/helpers/env_helper.py). Key patterns:
- Uses Azure Key Vault for secrets (via `SecretHelper`)
- Supports both `AZURE_AUTH_TYPE=keys` and `AZURE_AUTH_TYPE=rbac`
- Database type (`DATABASE_TYPE`) switches between `CosmosDB` (default) and `PostgreSQL`

### Conversation Flow Modes
Set via `CONVERSATION_FLOW` environment variable:
- `custom` - Uses pluggable orchestrators (Semantic Kernel, LangChain, OpenAI Functions)
- `byod` - Mimics Azure OpenAI "On Your Data" pattern

### Orchestration Strategies
Located in `code/backend/batch/utilities/orchestrator/`. The `ORCHESTRATION_STRATEGY` env var selects:
- `openai_function` - OpenAI function calling
- `langchain` - LangChain agent
- `semantic_kernel` - Microsoft Semantic Kernel
- `prompt_flow` - Azure ML Prompt Flow

## Build & Test Commands

```bash
# Install dependencies
poetry install                    # Python deps
cd code/frontend && npm install   # Frontend deps

# Run tests
make unittest                     # Python unit tests (excludes azure, functional markers)
make unittest-frontend            # Frontend Jest tests
make functionaltest               # Functional tests (require running server)
make lint                         # flake8 linting

# Local development
./start_local.sh                  # Starts Flask (5050) + Vite (5173)
./start_local.sh --skip-deps      # Faster startup when deps already installed
./stop_local.sh                   # Cleanup
```

## Supported File Types for Ingestion

The Admin UI (`01_Ingest_Data.py`) supports uploading: **PDF, TXT, HTML, MD, DOCX, JSON, CSV**, JPEG, JPG, PNG.

**CSV loading strategy:** `code/backend/batch/utilities/document_loading/csv_document.py`
- Reads CSV via HTTP, converts rows in chunks of 50 to `SourceDocument` records
- Each record is formatted as "Column: value, ..." for embedding

## Sales Data Schema (OrderHistoryLine)

| Column | Description |
|--------|-------------|
| Id | Record identifier |
| OrderType | Future / Standard |
| Status | OPEN / ALLOCATED / SHIPPED / CANCELLED |
| RequestedDeliveryDate | Customer requested date |
| ConfirmedDeliveryDate | Confirmed delivery date |
| RequestQuantity | Units ordered |
| UnitRetailPrice | RRP (consumer price) |
| UnitNetPrice | Net price paid by customer |
| Discount | Discount percentage |
| BrandId | Brand identifier (e.g. B_21) |
| ProductLineId | Product line (e.g. B_2102) |
| StyleNumber | Article/style number |
| CurrencyIsoAlpha3 | EUR / USD / DKK |

## Test Markers (pytest.ini)
- `@pytest.mark.unittest` - Fast unit tests
- `@pytest.mark.functional` - Tests requiring stubbed server
- `@pytest.mark.azure` - Extended tests hitting real Azure services

## Project Conventions

### Import Paths
Python imports use `code/` as the root (configured via `pythonpath = ./code` in pytest.ini):
```python
from backend.batch.utilities.helpers.env_helper import EnvHelper
from backend.batch.utilities.orchestrator.strategies import get_orchestrator
```

### Document Loading Pattern
All loaders in `code/backend/batch/utilities/document_loading/` extend `DocumentLoadingBase` and implement `load(document_url: str) -> List[SourceDocument]`.

### Configuration Storage
Runtime config stored in Azure Blob Storage (`config` container, `active.json` file). Default config (including system prompt) at `code/backend/batch/utilities/helpers/config/default.json`.

## Azure Deployment (azure.yaml)
Uses Azure Developer CLI (`azd`). The three services map to:
- `web` → Azure App Service (Flask + bundled React frontend)
- `adminweb` → Azure App Service (Streamlit)
- `function` → Azure Functions

## Key Files Reference
- Entry points: [code/app.py](code/app.py), [code/backend/Admin.py](code/backend/Admin.py), [code/backend/batch/function_app.py](code/backend/batch/function_app.py)
- Flask routes: [code/create_app.py](code/create_app.py)
- Default system prompt: [code/backend/batch/utilities/helpers/config/default.json](code/backend/batch/utilities/helpers/config/default.json)
- CSV loader: [code/backend/batch/utilities/document_loading/csv_document.py](code/backend/batch/utilities/document_loading/csv_document.py)
- Database connection UI: [code/backend/pages/05_Database_Connection.py](code/backend/pages/05_Database_Connection.py)

