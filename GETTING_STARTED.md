# Getting Started

The fastest path from zero to chatting with your data.

---

## Step 1: Deploy Azure Resources

Provision the required Azure infrastructure with one click. This creates Azure OpenAI, AI Search, Cosmos DB, Blob Storage, and App Service in your subscription.

> **Check quota first**: Follow the [quota check guide](docs/QuotaCheck.md) to ensure your subscription has enough Azure OpenAI capacity.

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Famir0135%2FSalesInsight-Foundry-POC%2Frefs%2Fheads%2Ffeature%2Ffoundry-migration%2Finfra%2Fmain.json)

During deployment:
- **Region**: Choose one of the [supported regions](#supported-azure-regions) listed in the README
- **Database Type**: Leave as **CosmosDB** (recommended for this POC)

> **Note:** The default deployment uses **GPT-4.1** (version 2025-04-14). Ensure this model is available in your chosen region.

When deployment is complete, [set up authentication in Azure App Service](docs/azure_app_service_auth_setup.md).

---

## Step 2: Clone and Run

```bash
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC

# Pull Azure config into .env and install dependencies
./scripts/setup_local.sh

# Start all services (installs/updates deps automatically)
./start_local.sh
```

The setup script will ask you for the **resource group name** you chose in Step 1. It discovers all deployed resources and generates a `.env` file automatically.

Open the **Chat UI** at **http://localhost:5173**.

> `start_local.sh` automatically creates a Python virtual environment, installs Python and Node.js dependencies, starts a local PostgreSQL container, and launches all four services. See [Local Development Guide](docs/LOCAL_DEVELOPMENT.md) for startup flags and troubleshooting.

---

## Step 3: Try It Out

### Document Q&A (RAG)

1. Open the **Admin UI** at http://localhost:8501
2. Go to **Ingest Data** → upload PDFs, Word docs, or other files
3. Return to the **Chat UI** and ask questions about your documents

### Sales Queries (NL2SQL)

By default, the POC uses **bundled CSV data** from the `data/` folder — no external database required. You can start asking sales questions right away:

```
What are the top 10 products by revenue?
Show me turnover by region for FY 25/26
Which customers have the highest order volume?
```

> **Want to connect Snowflake?** If you have a Snowflake account with an `ORDERHISTORYLINE` table, you can connect it via the **Admin UI → Database Connection** page, or by adding credentials to your `.env` file. See the [Snowflake setup guide](docs/snowflake_setup.md) for details. This is **optional** — the POC works fully without it.

---

## GitHub Codespaces (no local install)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/amir0135/SalesInsight-Foundry-POC?quickstart=1)

Add your Azure OpenAI and Snowflake credentials as **Codespace secrets** (Settings → Secrets and variables → Codespaces), then run `./start_local.sh --skip-azure` in the terminal.

---

## Next Steps

- **Docker setup, manual config, troubleshooting** → [Local Development Guide](docs/LOCAL_DEVELOPMENT.md)
- **Snowflake table setup** → [Snowflake Setup](docs/snowflake_setup.md)
- **Full feature list and architecture** → [README](README.md)
