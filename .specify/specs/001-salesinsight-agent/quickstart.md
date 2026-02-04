# Quickstart Guide: SalesInsight AI Agent

**Feature**: 001-salesinsight-agent  
**Date**: 2026-02-04

---

## Prerequisites

Before starting development, ensure you have:

1. **Python 3.11+** installed
2. **Poetry** for dependency management
3. **Node.js 18+** for frontend
4. **Azure CLI** (`az`) logged in
5. **Access to**:
   - Snowflake account with OrderHistoryLine data
   - Azure OpenAI with GPT-4o deployment
   - Azure AI Foundry project (optional for agent service)

---

## 1. Environment Setup

### Clone and Install Dependencies

```bash
# Clone repository
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC

# Install Python dependencies
poetry install

# Install frontend dependencies
cd code/frontend && npm install && cd ../..
```

### Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key  # Or use RBAC
AZURE_OPENAI_MODEL=gpt-4o

# Snowflake
SNOWFLAKE_ACCOUNT=your-account.region
SNOWFLAKE_USER=service_account
SNOWFLAKE_PASSWORD=your-password  # Or use Key Vault
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=SALES_DB
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_ROLE=SALES_READER

# Azure AI Foundry (optional)
AI_FOUNDRY_ENDPOINT=https://your-foundry.api.azureml.ms
AI_FOUNDRY_PROJECT=salesinsight-poc

# Existing settings
AZURE_AUTH_TYPE=rbac
DATABASE_TYPE=PostgreSQL
ORCHESTRATION_STRATEGY=ai_foundry  # New strategy option
```

---

## 2. Local Development

### Start Local Services

```bash
# Start PostgreSQL (for conversation history)
docker-compose -f docker/docker-compose.local.yml up -d

# Start Flask backend (port 5050)
cd code && poetry run python app.py

# In another terminal - Start frontend (port 5173)
cd code/frontend && npm run dev
```

### Access the Application

- **Chat UI**: http://localhost:5173
- **API**: http://localhost:5050

---

## 3. Running Tests

```bash
# Run all unit tests
make unittest

# Run specific test file
poetry run pytest code/tests/test_snowflake_datasource.py -v

# Run with coverage
poetry run pytest code/tests/ --cov=code/backend --cov-report=html

# Run security tests
poetry run pytest code/tests/test_sql_validator.py -v
```

---

## 4. Sample Queries

Once the system is running, try these queries in the chat interface:

### Basic Queries

```
What are the best sold styles?
Show me the top 10 products by revenue
How many orders do we have in France?
```

### Market & Brand Queries

```
What is the turnover in FY 25/26 in France for Brand X?
Compare sales in Germany vs Italy this year
Show me brand performance by market
```

### Collection Queries

```
What was the turnover on collection COL1 2025 in France?
Give me a breakdown of collection sales by category
Which collections performed best in Q4?
```

### Detailed Lists

```
Give me a list of styles we sold to [Customer] on collection COL1 2025
Show all orders for Brand X in Germany with color details
List products sold to [Holding] by variant
```

### Category Analysis

```
Give me an overview of the best sold items in Dresses category
What's the subcategory breakdown for Tops?
Compare Dresses vs Blouses turnover
```

---

## 5. API Usage

### Query Endpoint

```bash
curl -X POST http://localhost:5050/api/sales/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the best sold styles in France?",
    "session_id": "optional-session-id",
    "include_visualization": true
  }'
```

### Response Structure

```json
{
  "answer": "The top 5 best sold styles in France are:\n\n1. **STYLE-001**...",
  "chart": "data:image/png;base64,iVBORw0KGgo...",
  "data_preview": [
    {"StyleCode": "STYLE-001", "StyleName": "Classic Dress", "Quantity": 2450}
  ],
  "metadata": {
    "query_type": "aggregation",
    "execution_time_ms": 1250,
    "rows_returned": 5,
    "has_visualization": true
  }
}
```

---

## 6. Debugging

### View SQL Generation

Enable debug logging to see generated SQL:

```python
# In your .env
LOG_LEVEL=DEBUG
```

### Test SQL Validator

```python
from backend.batch.utilities.nl2sql.sql_validator import SQLValidator

validator = SQLValidator()
result = validator.validate("SELECT * FROM OrderHistoryLine LIMIT 10")
print(result)  # {"valid": True, "errors": []}
```

### Test Snowflake Connection

```python
from backend.batch.utilities.data_sources.snowflake_data_source import SnowflakeDataSource

ds = SnowflakeDataSource()
schema = ds.get_schema()
print(schema)
```

---

## 7. Deployment

### One-Click Azure Deployment

```bash
# Login to Azure
az login

# Initialize azd
azd init

# Deploy all resources
azd up
```

### Deploy Individual Services

```bash
# Deploy web service only
azd deploy web

# Deploy function app only
azd deploy function
```

---

## 8. Troubleshooting

### Connection Issues

| Issue | Solution |
|-------|----------|
| Snowflake connection failed | Check credentials and network access |
| Azure OpenAI timeout | Verify endpoint and API key |
| Chart not rendering | Check base64 encoding, try smaller dataset |

### Query Issues

| Issue | Solution |
|-------|----------|
| "Table not in allowlist" | Add table to `allowlist_config.yaml` |
| SQL syntax error | Check GPT-4o prompt engineering |
| No results returned | Verify data exists for filter criteria |

### Common Errors

```
Error: SQL validation failed
→ Check if all tables/columns are in allowlist

Error: Snowflake connection timeout
→ Verify warehouse is running, check network

Error: Chart generation failed  
→ Check matplotlib installation, verify data format
```

---

## 9. Development Workflow

1. **Pick a task** from `tasks.md`
2. **Create a feature branch**: `git checkout -b feature/task-1.1.1`
3. **Write tests first** (TDD approach)
4. **Implement the feature**
5. **Run tests**: `make unittest`
6. **Submit PR** with task reference

---

## 10. Key Files Reference

| File | Purpose |
|------|---------|
| `code/backend/batch/utilities/data_sources/` | Data source connectors |
| `code/backend/batch/utilities/nl2sql/` | NL2SQL engine |
| `code/backend/batch/utilities/visualization/` | Chart generation |
| `code/backend/batch/utilities/agents/` | AI Foundry integration |
| `code/backend/api/routes/sales_query.py` | API endpoint |
| `infra/main.bicep` | Azure infrastructure |
| `.specify/specs/001-salesinsight-agent/` | Feature specifications |
