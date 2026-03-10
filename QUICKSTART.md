# Quickstart: Test SalesInsight with Your Snowflake Account

Get the SalesInsight NL2SQL demo running in **under 10 minutes**.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/amir0135/SalesInsight-Foundry-POC?quickstart=1)

## What You Need

| Requirement | Where to get it |
|---|---|
| **Snowflake account** with a table called `ORDERHISTORYLINE` | [Snowflake signup](https://signup.snowflake.com/) or your existing account |
| **Azure OpenAI** resource with a GPT-4o deployment | [Azure Portal](https://portal.azure.com/#create/Microsoft.CognitiveServicesOpenAI) |
| Python 3.10+ *(not needed for Codespaces)* | [python.org](https://python.org) |
| Node.js 18+ *(not needed for Codespaces)* | [nodejs.org](https://nodejs.org) |

> **Don't have Snowflake data yet?** Use `--local` mode to test with the bundled CSV file — see [Option B](#option-b-local-csv-no-snowflake) below.

---

## Option 0: GitHub Codespaces (fastest — no local install)

Run everything in the cloud with a single click.

### 1. Add your secrets to GitHub

Go to your fork's **Settings → Secrets and variables → Codespaces** and add these secrets:

| Secret name | Value |
|---|---|
| `SNOWFLAKE_ACCOUNT` | Your account identifier, e.g. `xy12345.us-east-1` |
| `SNOWFLAKE_USER` | Your Snowflake username |
| `SNOWFLAKE_PASSWORD` | Your Snowflake password |
| `SNOWFLAKE_WAREHOUSE` | Warehouse name, e.g. `COMPUTE_WH` |
| `SNOWFLAKE_DATABASE` | Database name, e.g. `SALES_DB` |
| `SNOWFLAKE_SCHEMA` | Schema name, e.g. `ORDERS` |
| `AZURE_OPENAI_RESOURCE` | Your Azure OpenAI resource name |
| `AZURE_OPENAI_API_KEY` | Your Azure OpenAI API key |

### 2. Click the button

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/amir0135/SalesInsight-Foundry-POC?quickstart=1)

Codespaces will:
- Build the dev container (Python, Node.js, all tools pre-installed)
- Install all dependencies automatically
- Generate `.env` from your secrets
- Open `QUICKSTART.md` so you know what to do next

### 3. Start the app

Once the Codespace is ready, open the terminal and run:

```bash
./start_local.sh --skip-azure
```

The Chat UI will auto-forward — click the popup or go to the **Ports** tab and open port 5173.

### 4. Try it

```
What are the top 10 products by revenue?
Show me turnover by region for FY 25/26
```

> **No secrets configured?** You can still run the quickstart script interactively inside the Codespace:
> ```bash
> ./scripts/quickstart_snowflake.sh
> ```

---

## Option A: Snowflake local (recommended)

### 1. Set up your Snowflake table

If you don't have `ORDERHISTORYLINE` yet, run the SQL in [docs/snowflake_setup.md](docs/snowflake_setup.md) to create the table and load data.

### 2. Run the quickstart script

```bash
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC
./scripts/quickstart_snowflake.sh
```

The script will:
- Check that Python and Node.js are installed
- Ask for your Snowflake credentials (account, user, password, warehouse, database, schema)
- Ask for your Azure OpenAI resource name and API key
- **Test the Snowflake connection** before proceeding
- Install all dependencies (Python + Node.js)
- Start the Flask API and React frontend

### 3. Open the app

Go to **http://localhost:5173** and try:

```
What are the top 10 products by revenue?
Show me turnover by region for FY 25/26
Which customers have the highest order volume?
```

### 4. Stop

```bash
./stop_local.sh
```

---

## Option B: Local CSV (no Snowflake)

Test with the bundled sample data — no Snowflake account needed:

```bash
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC
./scripts/quickstart_snowflake.sh --local
```

This loads `data/db_more_weu_prod_dbo_OrderHistoryLine.csv` into an in-memory SQLite database. You still need Azure OpenAI for the natural language processing.

---

## Manual Setup (if you prefer)

If you'd rather configure things yourself:

```bash
# 1. Clone
git clone https://github.com/amir0135/SalesInsight-Foundry-POC.git
cd SalesInsight-Foundry-POC

# 2. Copy and edit .env
cp .env.example .env
# Fill in the SNOWFLAKE and AZURE OPENAI sections at the top of .env

# 3. Install dependencies
poetry install            # or: pip install -e .
cd code/frontend && npm install && cd ../..

# 4. Start
./start_local.sh
```

---

## Troubleshooting

### Snowflake connection fails

| Error | Fix |
|---|---|
| `Account not found` | Check format: `xy12345.us-east-1` (not a URL). Azure Snowflake: `account.azure-region.azure` |
| `Warehouse does not exist` | Verify warehouse name in Snowflake UI and that it's started |
| `Table not found` | Run the table creation SQL from [docs/snowflake_setup.md](docs/snowflake_setup.md) |
| `Authentication failed` | Double-check username/password. Consider creating a service user (see snowflake_setup.md) |

### Azure OpenAI errors

| Error | Fix |
|---|---|
| `Resource not found` | Use the resource **name** (e.g. `my-openai`), not the full URL |
| `401 Unauthorized` | Check your API key — get it from Azure Portal > your OpenAI resource > Keys |
| `Model not found` | Ensure you have a deployment named `gpt-4o` (or change `AZURE_OPENAI_MODEL` in .env) |

### Other issues

- **Port already in use**: Run `./stop_local.sh` first to kill any leftover processes
- **Python import errors**: Make sure you're using the virtual environment — `source .venv/bin/activate`
- **Full setup guide**: See [docs/SETUP.md](docs/SETUP.md) for Docker setup, Admin UI, and document RAG features

---

## What's Included

Once running, you can:

- **Ask natural language questions** about your sales data → generates SQL, runs it on Snowflake, returns results with charts
- **SQL security**: All queries are validated — only SELECT allowed, table/column allowlists enforced
- **Auto-generated charts**: Bar charts for ranked/grouped results
- **Natural language summaries**: LLM interprets raw data into conversational answers

For the full platform (document RAG, Admin UI, evaluation pipeline), see the main [README.md](README.md).
