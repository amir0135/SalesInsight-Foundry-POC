---
name: SalesInsight Foundry POC
description: AI-powered sales analytics with RAG document search and natural language SQL queries, built on Azure AI Foundry.
languages:
- python
- typescript
- bicep
- azdeveloper
products:
- azure-openai
- azure-cognitive-search
- azure-app-service
- azure
- azure-ai-foundry
- document-intelligence
- azure-functions
- azure-storage-accounts
page_type: sample
urlFragment: salesinsight-foundry-poc

---

# SalesInsight Foundry POC

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/amir0135/SalesInsight-Foundry-POC?quickstart=1)

An AI-powered sales analytics platform that combines **document-based RAG** (Retrieval-Augmented Generation) with **natural language SQL queries** against sales databases. Built on Azure OpenAI and Azure AI Foundry, with support for Snowflake and PostgreSQL data sources.

> Based on the [Chat with your data Solution Accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator), extended with NL2SQL capabilities, sales-focused analytics, and Azure AI Foundry Agent orchestration.

> **Want to test with your own Snowflake account?** Click the button above to open in Codespaces, or see [Getting Started](GETTING_STARTED.md) for local setup.

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [Use Cases](#use-cases)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Docker Quick Start](#docker-quick-start)
- [Configuration](#configuration)
  - [Orchestration Strategies](#orchestration-strategies)
  - [Database Sources](#database-sources)
  - [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Supporting Documentation](#supporting-documentation)
- [License](#license)

---

## Key Features

- **Natural Language to SQL**: Ask sales questions in plain English and get SQL results with auto-generated visualizations
- **Document-Based RAG**: Chat with uploaded PDFs, Word docs, and web content using Azure AI Search and Azure OpenAI
- **Sales Analytics**: Purpose-built for querying sales order history — best-selling styles, turnover by market/brand, collection performance, and fiscal year reporting
- **Azure AI Foundry Agent**: New orchestration strategy using Foundry Agent Service with thread-based tool calling
- **Multiple Orchestrators**: Choose from Semantic Kernel, LangChain, OpenAI Functions, Prompt Flow, or Foundry Agent
- **Multi-Database Support**: Query Snowflake (production) or PostgreSQL (local/analytics), with a local CSV fallback for development
- **Automatic Visualizations**: Bar charts generated from SQL query results
- **Admin UI**: Streamlit-based interface for document ingestion, data exploration, prompt configuration, and database connection management
- **SQL Validation**: Security guardrails enforce SELECT-only queries with table/column allowlists and dangerous pattern detection
- **Evaluation Pipeline**: Automated evaluation of query quality using Azure AI Foundry scoring
- **Chat History**: Persistent conversation tracking with PostgreSQL or Cosmos DB

---

## Architecture

The platform consists of three deployable services:

| Service | Path | Technology | Purpose |
|---------|------|------------|---------|
| **web** | `code/` | Flask + React | Chat API and frontend UI |
| **adminweb** | `code/backend/` | Streamlit | Document ingestion, configuration, and database connection management |
| **function** | `code/backend/batch/` | Azure Functions | Background document processing (chunking, embedding, indexing) |

```
┌──────────────────────────────────────────────────────────┐
│                        Users                             │
└──────┬────────────────────────────┬──────────────────────┘
       │                            │
       ▼                            ▼
  ┌──────────┐               ┌─────────────┐
  │ Chat UI  │               │  Admin UI   │
  │ (React)  │               │ (Streamlit) │
  └────┬─────┘               └─────┬───────┘
       │                           │
       └───────────┬───────────────┘
                   ▼
          ┌────────────────┐
          │   Flask API    │
          │  (Port 5050)   │
          └───────┬────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
  ┌───────────┐     ┌──────────────────┐
  │ Document  │     │  NL2SQL Engine   │
  │  Search   │     │ (SQL Generation, │
  │ (RAG via  │     │  Validation,     │
  │ AI Search)│     │  Visualization)  │
  └─────┬─────┘     └────────┬─────────┘
        │                    │
        └────────┬───────────┘
                 ▼
       ┌──────────────────┐
       │   Orchestrator   │
       │ Foundry Agent /  │
       │ Semantic Kernel /│
       │ LangChain / etc. │
       └────────┬─────────┘
                ▼
       ┌──────────────────┐
       │  Azure OpenAI    │
       └──────────────────┘

Data Sources:
├── Azure AI Search ─── Document vectors + RAG retrieval
├── Snowflake ───────── Production sales data (OrderHistoryLine)
├── PostgreSQL ──────── Local dev + chat history
├── Azure Blob Storage ─ Document staging + config
└── Cosmos DB ───────── Chat history (alternative to PostgreSQL)
```

### Data Flow

1. **Documents**: Uploaded via Admin UI → stored in Azure Blob Storage → Azure Functions chunk and embed → indexed in Azure AI Search
2. **Sales Queries**: User asks a natural language question → NL2SQL engine generates validated SQL → executes against Snowflake/PostgreSQL → results returned with optional chart
3. **Chat**: Queries hit Flask API → orchestrator retrieves context (documents and/or SQL results) → LLM generates response

---

## Use Cases

### Sales Analytics

Ask natural language questions about sales data:

```
"What are the best-selling products this quarter?"
"What is turnover in France for Brand X in FY 25/26?"
"Show me the top 10 styles by revenue"
"What was turnover on collection COL1 2025 in France?"
"Which customers have the highest order volume?"
```

Results include data tables and auto-generated bar charts where applicable.

### Document Q&A

Upload internal documents (contracts, product manuals, policies) and ask questions:

```
"Summarize the key terms of the supplier contract"
"What does the employee handbook say about remote work?"
"What are the product specifications for Model X?"
```

---

## Getting Started

Follow the [Getting Started guide](GETTING_STARTED.md) — it walks you through deploying Azure resources, cloning the repo, and running the app in three steps.

### Quick overview

```bash
# 1. Deploy Azure resources
azd up

# 2. Clone and configure
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC
./scripts/setup_local.sh

# 3. Start all services (auto-installs dependencies)
./start_local.sh
```

Open the **Chat UI** at http://localhost:5173.

### GitHub Codespaces (no local install)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/amir0135/SalesInsight-Foundry-POC?quickstart=1)

Add your secrets in repo **Settings → Secrets → Codespaces**, then run `./start_local.sh --skip-azure`.

### More options

- **Docker setup, manual config, troubleshooting** → [Local Development Guide](docs/LOCAL_DEVELOPMENT.md)
- **Snowflake NL2SQL quickstart** → Run `./scripts/quickstart_snowflake.sh`

---

## Configuration

### Orchestration Strategies

Set via the `ORCHESTRATION_STRATEGY` environment variable:

| Strategy | Description |
|----------|-------------|
| `semantic_kernel` | Microsoft Semantic Kernel agent |
| `openai_function` | Native OpenAI function calling |
| `langchain` | LangChain agent framework |
| `prompt_flow` | Azure ML Prompt Flow |
| `foundry_agent` | Azure AI Foundry Agent Service (thread-based tool calling) |

### Database Sources

The NL2SQL engine supports multiple data sources for sales queries. Configure via the Admin UI (**Database Connection** page) or `.env`:

| Source | Use Case | Key Environment Variables |
|--------|----------|--------------------------|
| **Snowflake** | Production sales data | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_DATABASE` |
| **PostgreSQL** | Local development / analytics | `POSTGRES_HOST`, `POSTGRES_PORT=5432` |
| **Local CSV** | Offline development fallback | Loads from `data/` directory |

For Snowflake setup details, see [docs/snowflake_setup.md](docs/snowflake_setup.md).
For PostgreSQL configuration, see [docs/postgreSQL.md](docs/postgreSQL.md).

### Environment Variables

All configuration loads through the `EnvHelper` singleton. Key variables:

```bash
# Azure OpenAI
AZURE_OPENAI_RESOURCE=your-resource
AZURE_OPENAI_MODEL=gpt-4.1

# Azure AI Search
AZURE_SEARCH_SERVICE=your-search-service
AZURE_SEARCH_INDEX=your-index

# Orchestration
ORCHESTRATION_STRATEGY=semantic_kernel    # or foundry_agent, langchain, etc.
CONVERSATION_FLOW=custom                  # or byod

# Database (chat history)
DATABASE_TYPE=CosmosDB                    # or PostgreSQL

# NL2SQL / Sales Queries
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Snowflake (optional)
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PASSWORD=your-password
SNOWFLAKE_DATABASE=your-database
```

---

## Deployment

Deployment uses the [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/) with Bicep templates.

> **Before deploying**: Check Azure OpenAI quota availability. See the [quota check guide](./docs/QuotaCheck.md).

### One-Click Deploy

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Famir0135%2FSalesInsight-Foundry-POC%2Frefs%2Fheads%2Ffeature%2Ffoundry-migration%2Finfra%2Fmain.json)

During deployment you will choose a **region** and **database type** (PostgreSQL or Cosmos DB). The default model is **GPT-4.1** (version 2025-04-14).

### CLI Deploy

```bash
# Provision Azure resources + deploy all services
azd up

# Or deploy services individually
azd deploy web          # Chat UI + API
azd deploy adminweb     # Admin UI
azd deploy function     # Background processing
```

All three services deploy as **Azure App Service** (Docker containers). The infrastructure is defined in [infra/main.bicep](infra/main.bicep).

### Supported Azure Regions

The solution supports the following regions:

- **Australia East**
- **East US 2**
- **Japan East**
- **UK South**

### Post-Deployment

1. [Set up authentication in Azure App Service](./docs/azure_app_service_auth_setup.md)
2. Navigate to the Admin UI to upload documents and configure database connections
3. Open the Chat UI to start querying

---

## Testing

```bash
# Python unit tests
make unittest

# Frontend tests (Jest)
make unittest-frontend

# Functional tests (requires running server)
make functionaltest

# Linting
make lint

# NL2SQL evaluation (offline, no LLM required)
make evaluate

# NL2SQL evaluation with LLM scoring
make evaluate-llm

# Full evaluation with Azure AI Foundry scoring
make evaluate-full

# Regenerate golden dataset from current data
make generate-eval-dataset
```

Test markers (in `pytest.ini`):
- `@pytest.mark.unittest` — Fast unit tests
- `@pytest.mark.functional` — Tests requiring a stubbed server
- `@pytest.mark.azure` — Extended tests hitting real Azure services

---

## Project Structure

```
├── code/
│   ├── app.py                          # Flask entry point
│   ├── create_app.py                   # Flask route definitions
│   ├── frontend/                       # React chat UI (Vite + TypeScript)
│   ├── backend/
│   │   ├── Admin.py                    # Streamlit admin entry point
│   │   ├── pages/                      # Admin UI pages
│   │   │   ├── 01_Ingest_Data.py
│   │   │   ├── 02_Explore_Data.py
│   │   │   ├── 03_Delete_Data.py
│   │   │   ├── 04_Configuration.py
│   │   │   └── 05_Database_Connection.py
│   │   └── batch/
│   │       ├── function_app.py         # Azure Functions entry point
│   │       └── utilities/
│   │           ├── orchestrator/       # Orchestration strategies
│   │           │   ├── strategies.py
│   │           │   ├── semantic_kernel.py
│   │           │   ├── foundry_agent.py
│   │           │   ├── lang_chain_agent.py
│   │           │   └── ...
│   │           ├── nl2sql/             # Natural language to SQL engine
│   │           │   ├── sql_generator.py
│   │           │   ├── query_validator.py
│   │           │   └── prompt_builder.py
│   │           ├── visualization/      # Chart generation
│   │           ├── helpers/            # EnvHelper, config, database connectors
│   │           ├── document_loading/   # File type handlers
│   │           └── document_chunking/  # Chunking strategies
│   └── tests/                          # Unit and functional tests
├── data/                               # Sample data (CSV, contracts, search schema)
├── docker/                             # Dockerfiles and docker-compose configs
├── docs/                               # Setup guides, architecture docs, ADRs
├── infra/                              # Bicep templates for Azure deployment
├── scripts/                            # Setup, packaging, and evaluation scripts
│   ├── evaluation/                     # Golden dataset and evaluation runner
│   └── data_scripts/                   # Data preparation utilities
├── start_local.sh                      # Start all local services
├── stop_local.sh                       # Stop all local services
├── azure.yaml                          # Azure Developer CLI service definitions
├── pyproject.toml                      # Python dependencies (Poetry)
└── Makefile                            # Build, test, and lint commands
```

---

## Supporting Documentation

- [Local Development Guide](docs/LOCAL_DEVELOPMENT.md)
- [Database Integration](docs/database_integration.md)
- [Database AI Query Implementation](docs/database_ai_query_implementation.md)
- [Snowflake Setup](docs/snowflake_setup.md)
- [PostgreSQL Configuration](docs/postgreSQL.md)
- [Conversation Flow Options](docs/conversation_flow_options.md)
- [Integrated Vectorization](docs/integrated_vectorization.md)
- [Supported File Types](docs/supported_file_types.md)
- [Speech to Text](docs/speech_to_text.md)
- [Prompt Flow](docs/prompt_flow.md)
- [Model Configuration](docs/model_configuration.md)

### Azure Service Documentation

- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/)
- [Azure Document Intelligence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/)
- [Azure Application Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)

---

## License

This repository is licensed under the [MIT License](LICENSE.md).

Some sample data included in this repository was generated using AI and is for illustrative purposes only.
