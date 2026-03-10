# Getting Started

The fastest path from zero to chatting with your data.

---

## Step 1: Deploy Azure Resources

Provision the required Azure infrastructure first. This creates Azure OpenAI, AI Search, Cosmos DB, Blob Storage, and App Service in your subscription.

> **Check quota first**: Follow the [quota check guide](docs/QuotaCheck.md) to ensure your subscription has enough Azure OpenAI capacity.

```bash
az login
azd auth login
azd up
```

You'll be prompted for a region and database type (CosmosDB is the default). Once complete, `azd` outputs the URLs for your deployed services.

---

## Step 2: Clone and Run

```bash
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC

# Pull Azure config into .env
./scripts/setup_local.sh

# Install dependencies
poetry install
cd code/frontend && npm install && cd ../..

# Start all services
./start_local.sh
```

Open the **Chat UI** at **http://localhost:5173**.

---

## Step 3: Try It Out

### Document Q&A (RAG)

1. Open the **Admin UI** at http://localhost:8501
2. Go to **Ingest Data** → upload PDFs, Word docs, or other files
3. Return to the **Chat UI** and ask questions about your documents

### Sales Queries (NL2SQL)

If you have a Snowflake account with an `ORDERHISTORYLINE` table, connect it via the Admin UI or `.env` ([Snowflake setup guide](docs/snowflake_setup.md)). Then try:

```
What are the top 10 products by revenue?
Show me turnover by region for FY 25/26
Which customers have the highest order volume?
```

**No Snowflake?** Run `./scripts/quickstart_snowflake.sh --local` to test with the bundled CSV data.

---

## GitHub Codespaces (no local install)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/amir0135/SalesInsight-Foundry-POC?quickstart=1)

Add your Azure OpenAI and Snowflake credentials as **Codespace secrets** (Settings → Secrets and variables → Codespaces), then run `./start_local.sh --skip-azure` in the terminal.

---

## Next Steps

- **Docker setup, manual config, troubleshooting** → [Local Development Guide](docs/LOCAL_DEVELOPMENT.md)
- **Snowflake table setup** → [Snowflake Setup](docs/snowflake_setup.md)
- **Full feature list and architecture** → [README](README.md)
