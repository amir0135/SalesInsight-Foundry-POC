# Local Development Setup Guide

This guide explains how to set up the **Chat With Your Data** solution accelerator for local development.

---

## 🚀 Quick Start (Choose One)

### Option 1: Docker (Easiest - 5 minutes)

**Prerequisites:** Only [Docker Desktop](https://www.docker.com/products/docker-desktop) required.

```bash
# 1. Clone the repository
git clone https://github.com/amir0135/chat-with-your-data.git
cd chat-with-your-data

# 2. Create your config file
cp .env.example .env

# 3. Edit .env with your Azure OpenAI and Search credentials
#    (Only need: AZURE_OPENAI_*, AZURE_SEARCH_*, AZURE_BLOB_*)

# 4. Start everything
docker-compose -f docker/docker-compose.local.yml up --build

# 5. Open the app
#    Chat UI: http://localhost:8080
#    Admin UI: http://localhost:8501
```

To stop: `docker-compose -f docker/docker-compose.local.yml down`

---

### Option 2: Full Development Setup (Recommended for developers)

**Prerequisites:** Run the installer to get all required tools:

```bash
# Clone first
git clone https://github.com/amir0135/chat-with-your-data.git
cd chat-with-your-data

# Install all prerequisites (macOS/Linux)
./scripts/install_prerequisites.sh
```

<details>
<summary>Or install manually</summary>

- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Node.js 20+](https://nodejs.org)
- [Python 3.11+](https://www.python.org)
- [Poetry](https://python-poetry.org/docs/#installation)
- Azure Functions Core Tools: `npm install -g azure-functions-core-tools@4`

</details>

**Then deploy and configure:**

```bash
# 1. Login to Azure
az login
azd auth login

# 2. Deploy to Azure (creates all required resources)
azd up

# 3. Configure local environment (pulls config from Azure)
./scripts/setup_local.sh

# 4. Start all services
./start_local.sh

# 5. Open the app
#    Chat UI: http://localhost:5173
#    Admin UI: http://localhost:8501
```

---

### Option 3: Manual Setup (Advanced)

If you already have Azure resources and want manual control:

```bash
# 1. Install dependencies
poetry install
cd code/frontend && npm install && cd ../..

# 2. Configure environment
cp .env.example .env
# Edit .env with your Azure resource values

# 3. Start services
./start_local.sh
```

---

## 📋 Services Overview

| Service | Port | URL | Description |
|---------|------|-----|-------------|
| Chat UI | 5173 (dev) / 8080 (docker) | http://localhost:5173 | React frontend for chatting |
| Chat API | 5050 | http://localhost:5050 | Flask backend API |
| Admin UI | 8501 | http://localhost:8501 | Streamlit for document ingestion |
| Azure Functions | 7071 | http://localhost:7071 | Background document processing |
| PostgreSQL | 5432 | localhost:5432 | Local database for testing |

---

## 📊 Data Visualization

Query results are automatically analyzed and displayed as charts:

| Chart Type | Use Case | Example |
|------------|----------|---------|
| **Bar** | Compare values across categories | Errors by facility |
| **Line** | Trends over time | Daily error counts |
| **Pie** | Proportional breakdowns | Error type distribution |
| **Area** | Cumulative time-series | Sessions over time |

Charts appear above data tables with a type selector to switch between views.

---

---

## Database Integration

This includes **database integration** for querying operational data via natural language.

### Features
- Natural language to SQL conversion
- Query errors, connectivity, sessions, and facility data
- Smart schema retrieval (only loads relevant tables)
- **Data visualization** - automatically generates charts based on query results
- Works with PostgreSQL (local) or AWS Redshift (production)

### Example Queries
- "How many total errors occurred in the last 7 days?"
- "Which facility has the most errors?"
- "Show connectivity status for facilities with high error rates"
- "What's the average session duration this month?"

### Local Testing with PostgreSQL

The `start_local.sh` script automatically starts a PostgreSQL container with test data:

```bash
# PostgreSQL connection (auto-configured)
Host: localhost
Port: 5432
Database: database_test
User: testuser
Password: testpassword
```

### Loading Test Data

To populate the test database with sample data:

```bash
# The test data is auto-loaded from data/testtrack/
# Or manually run:
python -c "from code.backend.batch.utilities.helpers.database.load_test_data import load_all_test_data; load_all_test_data()"
```

### Production Redshift Configuration

For production, update `.env`:

```bash
REDSHIFT_HOST=your-cluster.region.redshift.amazonaws.com
REDSHIFT_PORT=5439
REDSHIFT_DB=your_database
REDSHIFT_USER=your_user
REDSHIFT_PASSWORD=your_password
```

## Document Ingestion

1. Open **Admin UI** at http://localhost:8501
2. Go to "Ingest Data" page
3. Upload PDF, Word, or other supported documents
4. Documents are automatically processed and indexed

## Troubleshooting

### Flask won't start
```bash
# Check the log
tail -f /tmp/flask.log

# Common fix: ensure .env exists and .venv is activated
source .venv/bin/activate
```

### Azure Functions won't start
```bash
# Check the log
tail -f /tmp/functions.log

# Install Azure Functions Core Tools if missing
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
# Stop and remove container
docker stop database-postgres
docker rm database-postgres

# Restart (start_local.sh will recreate it)
./start_local.sh
```

## Stopping Services

```bash
./stop_local.sh
```

To also stop PostgreSQL:
```bash
docker stop database-postgres
```

## File Structure

```
├── start_local.sh          # Start all services
├── stop_local.sh           # Stop all services
├── scripts/
│   └── setup_local.sh      # One-time setup (pulls from Azure)
├── .env                    # Environment configuration
├── .env.sample             # Template for .env
├── code/
│   ├── app.py              # Flask entry point
│   ├── frontend/           # React/Vite frontend
│   ├── backend/
│   │   ├── Admin.py        # Streamlit admin entry
│   │   └── batch/
│   │       ├── local.settings.json  # Azure Functions config
│   │       └── utilities/helpers/database/  # Database integration
└── data/
    └── testtrack/          # Test data for Database
```

## Azure Resources Required

After `azd up`, you'll have:
- Azure OpenAI (GPT-4 + embeddings)
- Azure AI Search (document indexing)
- Azure Blob Storage (document storage)
- Azure Cosmos DB (conversation history)
- Azure Functions (background processing)
- Azure Key Vault (secrets management)
