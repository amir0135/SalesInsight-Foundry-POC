#!/bin/bash
# =============================================================================
# Local Development Startup Script
# =============================================================================
# Starts all services: Chat UI (Flask + Vite), Admin UI (Streamlit),
# Azure Functions, and PostgreSQL (for TrackMan testing)
#
# Prerequisites:
#   - Run ./scripts/setup_local.sh first (after azd up)
#   - Or manually create .env and install dependencies
#
# Usage:
#   ./start_local.sh              # Full startup with Azure config
#   ./start_local.sh --skip-azure # Skip Azure policy configuration
#   ./start_local.sh --skip-deps  # Skip dependency check (faster startup)
# =============================================================================

set -e

# Parse command line arguments
SKIP_AZURE=false
SKIP_DEPS=false
for arg in "$@"; do
    case $arg in
        --skip-azure)
            SKIP_AZURE=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --fast)
            # Fast mode: skip both Azure and deps
            SKIP_AZURE=true
            SKIP_DEPS=true
            shift
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Chat With Your Data - Local Development Environment      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Pre-flight Checks
# =============================================================================
echo -e "${BLUE}[Preflight] Checking setup...${NC}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found.${NC}"
    echo -e "${YELLOW}  Run ./scripts/setup_local.sh first, or copy .env.sample to .env${NC}"
    exit 1
fi

# =============================================================================
# Azure Credentials Refresh
# =============================================================================
# Refreshes Azure CLI token to ensure Cosmos DB and other Azure services work.
# Tokens expire daily, so this runs on every startup unless --skip-azure is used.

refresh_azure_credentials() {
    echo -e "${BLUE}[Azure] Checking Azure credentials...${NC}"

    # Check if using RBAC authentication
    AUTH_TYPE=$(grep -E "^AZURE_AUTH_TYPE=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "keys")

    if [ "$AUTH_TYPE" != "rbac" ]; then
        echo -e "${GREEN}  ✓ Using key-based auth, no token refresh needed${NC}"
        return 0
    fi

    # Check if az CLI is installed
    if ! command -v az &> /dev/null; then
        echo -e "${YELLOW}⚠ Azure CLI not installed. RBAC auth may fail.${NC}"
        return 0
    fi

    # Check if logged in and token is valid
    if ! az account get-access-token --query "expiresOn" -o tsv > /dev/null 2>&1; then
        echo -e "${YELLOW}  Azure token expired or not logged in. Refreshing...${NC}"

        # Try to refresh silently first (works if session is still valid)
        if az account get-access-token --resource https://cosmos.azure.com > /dev/null 2>&1; then
            echo -e "${GREEN}  ✓ Azure token refreshed${NC}"
        else
            echo -e "${YELLOW}  Opening browser for Azure login...${NC}"
            if az login --only-show-errors > /dev/null 2>&1; then
                echo -e "${GREEN}  ✓ Azure login successful${NC}"
            else
                echo -e "${RED}✗ Azure login failed. Cosmos DB access may not work.${NC}"
                echo -e "${YELLOW}  Run 'az login' manually if needed.${NC}"
            fi
        fi
    else
        # Token exists, verify it's not about to expire (within 5 minutes)
        EXPIRES_ON=$(az account get-access-token --query "expiresOn" -o tsv 2>/dev/null || echo "")
        if [ -n "$EXPIRES_ON" ]; then
            # macOS date command
            EXPIRES_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "${EXPIRES_ON%.*}" "+%s" 2>/dev/null || echo "0")
            NOW_EPOCH=$(date "+%s")
            REMAINING=$((EXPIRES_EPOCH - NOW_EPOCH))

            if [ "$REMAINING" -lt 300 ] 2>/dev/null; then
                echo -e "${YELLOW}  Token expiring soon, refreshing...${NC}"
                az account get-access-token --resource https://management.azure.com > /dev/null 2>&1 || true
            fi
            echo -e "${GREEN}  ✓ Azure credentials valid${NC}"
        else
            echo -e "${GREEN}  ✓ Azure credentials valid${NC}"
        fi
    fi
}

if [ "$SKIP_AZURE" = false ]; then
    refresh_azure_credentials
fi

# =============================================================================
# Python Environment Setup
# =============================================================================
# Ensures venv exists and all dependencies are installed - works on any computer

setup_python_environment() {
    echo -e "${BLUE}[Python] Setting up Python environment...${NC}"

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}  Creating virtual environment...${NC}"
        # Detect Python 3 executable for venv creation
        if command -v python3.11 &> /dev/null; then
            PYTHON_CREATE="python3.11"
        elif command -v python3 &> /dev/null; then
            PYTHON_CREATE="python3"
        elif command -v python &> /dev/null; then
            PYTHON_CREATE="python"
        else
            echo -e "${RED}✗ Python not found. Please install Python 3.10+${NC}"
            exit 1
        fi
        $PYTHON_CREATE -m venv .venv
        echo -e "${GREEN}  ✓ Virtual environment created${NC}"
    fi

    # Use venv's Python and pip explicitly (not shell aliases)
    VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
    VENV_PIP="$SCRIPT_DIR/.venv/bin/pip"

    PYTHON_VERSION=$($VENV_PYTHON --version 2>&1 | cut -d' ' -f2)
    echo -e "${BLUE}  Using venv Python: $PYTHON_VERSION${NC}"

    # Upgrade pip to avoid issues
    echo -e "${YELLOW}  Ensuring pip is up to date...${NC}"
    $VENV_PIP install --upgrade pip --quiet 2>/dev/null || true

    # Install/sync dependencies using pip with requirements
    # First check if we need to install dependencies
    DEPS_MARKER=".venv/.deps_installed"
    PYPROJECT_HASH=$(md5 -q pyproject.toml 2>/dev/null || md5sum pyproject.toml | cut -d' ' -f1)

    NEEDS_INSTALL=false
    if [ ! -f "$DEPS_MARKER" ]; then
        NEEDS_INSTALL=true
    elif [ "$(cat $DEPS_MARKER 2>/dev/null)" != "$PYPROJECT_HASH" ]; then
        NEEDS_INSTALL=true
        echo -e "${YELLOW}  pyproject.toml changed, reinstalling dependencies...${NC}"
    fi

    if [ "$NEEDS_INSTALL" = true ]; then
        echo -e "${YELLOW}  Installing Python dependencies (this may take a few minutes)...${NC}"

        # Try poetry first if available and configured to use our venv
        if command -v poetry &> /dev/null; then
            echo -e "${BLUE}  Using poetry to install dependencies...${NC}"
            poetry config virtualenvs.in-project true 2>/dev/null || true
            poetry install --no-interaction 2>&1 | grep -E "(Installing|Already installed|✓)" || true
        else
            echo -e "${BLUE}  Poetry not found, using pip...${NC}"
            # Install core dependencies directly with venv's pip
            $VENV_PIP install --quiet \
                "azure-functions==1.23.0" \
                "streamlit==1.50.0" \
                "python-dotenv==1.1.1" \
                "azure-ai-formrecognizer==3.3.3" \
                "azure-storage-blob==12.26.0" \
                "azure-identity==1.25.0" \
                "flask[async]>=3.1.2" \
                "openai==1.109.1" \
                "langchain==0.2.17" \
                "langchain-community==0.2.19" \
                "langchain-openai==0.1.25" \
                "requests==2.32.5" \
                "tiktoken==0.11.0" \
                "azure-storage-queue==12.13.0" \
                "beautifulsoup4==4.14.2" \
                "fake-useragent==2.2.0" \
                "chardet==5.2.0" \
                "azure-search-documents==11.6.0b1" \
                "azure-ai-contentsafety==1.0.0" \
                "python-docx==1.2.0" \
                "azure-keyvault-secrets==4.10.0" \
                "pandas==2.3.3" \
                "pillow==11.0.0" \
                "azure-mgmt-cognitiveservices>=14.0.0" \
                "jsonschema>=4.25.1" \
                "pydantic==2.11.9" \
                "azure-ai-ml>=1.29.0" \
                "azure-cosmos>=4.7.0" \
                "asyncpg>=0.30.0" \
                "psycopg2-binary>=2.9.10" \
                "pgvector>=0.4.1" \
                "azure-ai-projects>=1.0.0" \
                "azure-ai-evaluation>=1.0.0" \
                "pyyaml>=6.0.3" \
                2>&1 | tail -5

            # Install OpenTelemetry packages with compatible versions
            $VENV_PIP install --quiet \
                "azure-monitor-opentelemetry>=1.6.10" \
                "azure-core-tracing-opentelemetry>=1.0.0b12" \
                "opentelemetry-api==1.39.0" \
                "opentelemetry-sdk==1.39.0" \
                "opentelemetry-semantic-conventions==0.60b0" \
                "opentelemetry-instrumentation==0.60b0" \
                "opentelemetry-util-http==0.60b0" \
                "opentelemetry-instrumentation-httpx==0.60b0" \
                2>&1 | tail -3

            # Install semantic-kernel only for Python < 3.13
            PYTHON_MINOR=$($VENV_PYTHON -c "import sys; print(sys.version_info.minor)")
            if [ "$PYTHON_MINOR" -lt 13 ]; then
                $VENV_PIP install --quiet "semantic-kernel==1.37.0" 2>&1 | tail -1 || true
            fi

            # Install dev dependencies
            $VENV_PIP install --quiet pytest pytest-cov flake8 pytest-asyncio 2>&1 | tail -1 || true
        fi

        # Mark dependencies as installed
        echo "$PYPROJECT_HASH" > "$DEPS_MARKER"
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    else
        echo -e "${GREEN}  ✓ Python dependencies up to date${NC}"
    fi

    # Verify critical imports work
    echo -e "${YELLOW}  Verifying critical imports...${NC}"
    if $VENV_PYTHON -c "from flask import Flask; from azure.keyvault.secrets import SecretClient; from azure.monitor.opentelemetry import configure_azure_monitor; from langchain_community.vectorstores import AzureSearch; print('OK')" 2>/dev/null; then
        echo -e "${GREEN}  ✓ Critical imports verified${NC}"
    else
        echo -e "${YELLOW}  ⚠ Some imports failed, attempting to fix...${NC}"
        $VENV_PIP install --quiet --force-reinstall \
            "azure-keyvault-secrets==4.10.0" \
            "azure-monitor-opentelemetry>=1.6.10" \
            "opentelemetry-instrumentation-httpx==0.60b0" \
            "langchain==0.2.17" \
            "langchain-community==0.2.19" \
            2>&1 | tail -3
    fi
}

# Setup Python environment (unless --skip-deps flag is passed)
if [ "$SKIP_DEPS" = true ]; then
    echo -e "${YELLOW}[Python] Skipping dependency check (--skip-deps flag)${NC}"
    # Still need to activate the venv
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo -e "${RED}✗ Virtual environment not found. Cannot use --skip-deps on first run.${NC}"
        exit 1
    fi
else
    setup_python_environment
fi

# Check if node_modules exists
if [ ! -d "code/frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠ Frontend dependencies not installed. Installing...${NC}"
    cd code/frontend && npm install && cd ../..
elif [ "$SKIP_DEPS" = false ]; then
    # Check if package.json changed
    PACKAGE_HASH=$(md5 -q code/frontend/package.json 2>/dev/null || md5sum code/frontend/package.json | cut -d' ' -f1)
    PACKAGE_MARKER="code/frontend/node_modules/.package_hash"
    if [ ! -f "$PACKAGE_MARKER" ] || [ "$(cat $PACKAGE_MARKER 2>/dev/null)" != "$PACKAGE_HASH" ]; then
        echo -e "${YELLOW}⚠ Frontend package.json changed. Reinstalling...${NC}"
        cd code/frontend && npm install && cd ../..
        echo "$PACKAGE_HASH" > "$PACKAGE_MARKER"
    fi
fi

# Check if local.settings.json exists
if [ ! -f "code/backend/batch/local.settings.json" ]; then
    echo -e "${YELLOW}⚠ local.settings.json not found. Creating default...${NC}"
    cat > code/backend/batch/local.settings.json << 'EOF'
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true"
  },
  "ConnectionStrings": {}
}
EOF
    echo -e "${YELLOW}  Note: Document processing may not work without proper Azure storage config.${NC}"
    echo -e "${YELLOW}  Run ./scripts/setup_local.sh for full Azure integration.${NC}"
fi

echo -e "${GREEN}✓ Setup checks passed${NC}"
echo ""

# =============================================================================
# Azure Policy Auto-Fix
# =============================================================================
# Handles daily subscription policy resets that disable public network access
# and remove role assignments. Run automatically on every startup.

configure_azure_storage() {
    echo -e "${BLUE}[Azure] Configuring Azure Storage for local development...${NC}"

    # Check if az CLI is logged in
    if ! az account show > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Azure CLI not logged in. Skipping Azure configuration.${NC}"
        echo -e "${YELLOW}  Run 'az login' if you need Azure Storage access.${NC}"
        return 0
    fi

    # Get storage account name from .env
    STORAGE_ACCOUNT=$(grep -E "^AZURE_BLOB_ACCOUNT_NAME=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || true)

    if [ -z "$STORAGE_ACCOUNT" ]; then
        echo -e "${YELLOW}⚠ AZURE_BLOB_ACCOUNT_NAME not found in .env. Skipping Azure configuration.${NC}"
        return 0
    fi

    # Get resource group from .env or azd
    RESOURCE_GROUP=$(grep -E "^AZURE_RESOURCE_GROUP=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || true)
    if [ -z "$RESOURCE_GROUP" ]; then
        RESOURCE_GROUP=$(azd env get-values 2>/dev/null | grep "^AZURE_RESOURCE_GROUP=" | cut -d'=' -f2 | tr -d '"' || true)
    fi

    if [ -z "$RESOURCE_GROUP" ]; then
        echo -e "${YELLOW}⚠ AZURE_RESOURCE_GROUP not found. Trying to auto-detect...${NC}"
        RESOURCE_GROUP=$(timeout 15 az storage account show --name "$STORAGE_ACCOUNT" --query "resourceGroup" -o tsv 2>/dev/null || true)
    fi

    if [ -z "$RESOURCE_GROUP" ]; then
        echo -e "${YELLOW}⚠ Could not determine resource group. Skipping Azure configuration.${NC}"
        return 0
    fi

    echo -e "${BLUE}  Storage Account: $STORAGE_ACCOUNT${NC}"
    echo -e "${BLUE}  Resource Group: $RESOURCE_GROUP${NC}"

    # 1. Enable public network access on storage account
    echo -e "${YELLOW}  Enabling public network access on storage account...${NC}"
    timeout 30 az storage account update \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --public-network-access Enabled \
        --default-action Allow \
        --output none 2>/dev/null && \
        echo -e "${GREEN}  ✓ Public network access enabled${NC}" || \
        echo -e "${YELLOW}  ⚠ Could not update network access (may already be enabled or insufficient permissions)${NC}"

    # 2. Ensure current user has Storage Blob Data Contributor role
    echo -e "${YELLOW}  Checking Storage Blob role assignments...${NC}"
    CURRENT_USER_ID=$(timeout 15 az ad signed-in-user show --query id -o tsv 2>/dev/null || true)

    if [ -n "$CURRENT_USER_ID" ]; then
        STORAGE_ACCOUNT_ID=$(timeout 15 az storage account show \
            --name "$STORAGE_ACCOUNT" \
            --resource-group "$RESOURCE_GROUP" \
            --query id -o tsv 2>/dev/null || true)

        if [ -n "$STORAGE_ACCOUNT_ID" ]; then
            # Check if role is already assigned
            EXISTING_ROLE=$(timeout 30 az role assignment list \
                --assignee "$CURRENT_USER_ID" \
                --scope "$STORAGE_ACCOUNT_ID" \
                --role "Storage Blob Data Contributor" \
                --query "[0].id" -o tsv 2>/dev/null || true)

            if [ -z "$EXISTING_ROLE" ]; then
                echo -e "${YELLOW}  Assigning Storage Blob Data Contributor role...${NC}"
                timeout 30 az role assignment create \
                    --assignee "$CURRENT_USER_ID" \
                    --role "Storage Blob Data Contributor" \
                    --scope "$STORAGE_ACCOUNT_ID" \
                    --output none 2>/dev/null && \
                    echo -e "${GREEN}  ✓ Storage Blob Data Contributor role assigned${NC}" || \
                    echo -e "${YELLOW}  ⚠ Could not assign role (may require elevated permissions)${NC}"
            else
                echo -e "${GREEN}  ✓ Storage Blob Data Contributor role already assigned${NC}"
            fi

            # Also ensure Storage Blob Delegator role for SAS token generation
            DELEGATOR_ROLE=$(timeout 30 az role assignment list \
                --assignee "$CURRENT_USER_ID" \
                --scope "$STORAGE_ACCOUNT_ID" \
                --role "Storage Blob Delegator" \
                --query "[0].id" -o tsv 2>/dev/null || true)

            if [ -z "$DELEGATOR_ROLE" ]; then
                echo -e "${YELLOW}  Assigning Storage Blob Delegator role...${NC}"
                timeout 30 az role assignment create \
                    --assignee "$CURRENT_USER_ID" \
                    --role "Storage Blob Delegator" \
                    --scope "$STORAGE_ACCOUNT_ID" \
                    --output none 2>/dev/null && \
                    echo -e "${GREEN}  ✓ Storage Blob Delegator role assigned${NC}" || \
                    echo -e "${YELLOW}  ⚠ Could not assign role (may require elevated permissions)${NC}"
            else
                echo -e "${GREEN}  ✓ Storage Blob Delegator role already assigned${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}  ⚠ Could not get current user ID. Skipping role assignments.${NC}"
    fi

    # 3. Allow blob public access (if required by policies)
    echo -e "${YELLOW}  Configuring blob public access settings...${NC}"
    timeout 30 az storage account update \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --allow-blob-public-access true \
        --output none 2>/dev/null && \
        echo -e "${GREEN}  ✓ Blob public access configured${NC}" || \
        echo -e "${YELLOW}  ⚠ Could not update blob public access setting${NC}"

    echo -e "${GREEN}✓ Azure Storage configuration complete${NC}"
    echo ""
}

# Configure Cosmos DB RBAC permissions
configure_cosmos_db() {
    echo -e "${BLUE}[Azure] Configuring Cosmos DB for local development...${NC}"

    # Check if using Cosmos DB
    DATABASE_TYPE=$(grep -E "^DATABASE_TYPE=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "CosmosDB")
    if [ "$DATABASE_TYPE" != "CosmosDB" ]; then
        echo -e "${YELLOW}  Skipping - DATABASE_TYPE is $DATABASE_TYPE, not CosmosDB${NC}"
        return 0
    fi

    # Get Cosmos DB account name from .env
    COSMOS_ACCOUNT=$(grep -E "^AZURE_COSMOSDB_ACCOUNT_NAME=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || true)

    if [ -z "$COSMOS_ACCOUNT" ]; then
        echo -e "${YELLOW}⚠ AZURE_COSMOSDB_ACCOUNT_NAME not found in .env. Skipping Cosmos DB configuration.${NC}"
        return 0
    fi

    # Get resource group from .env or auto-detect
    RESOURCE_GROUP=$(grep -E "^AZURE_RESOURCE_GROUP=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || true)
    if [ -z "$RESOURCE_GROUP" ]; then
        RESOURCE_GROUP=$(timeout 15 az cosmosdb show --name "$COSMOS_ACCOUNT" --query "resourceGroup" -o tsv 2>/dev/null || true)
    fi

    if [ -z "$RESOURCE_GROUP" ]; then
        echo -e "${YELLOW}⚠ Could not determine resource group. Skipping Cosmos DB configuration.${NC}"
        return 0
    fi

    echo -e "${BLUE}  Cosmos DB Account: $COSMOS_ACCOUNT${NC}"
    echo -e "${BLUE}  Resource Group: $RESOURCE_GROUP${NC}"

    # Enable public network access on Cosmos DB (policies may disable this daily)
    echo -e "${YELLOW}  Enabling public network access on Cosmos DB...${NC}"
    for attempt in 1 2 3; do
        if timeout 90 az cosmosdb update \
            --name "$COSMOS_ACCOUNT" \
            --resource-group "$RESOURCE_GROUP" \
            --public-network-access ENABLED \
            --output none 2>/dev/null; then
            echo -e "${GREEN}  ✓ Public network access enabled${NC}"
            break
        else
            if [ $attempt -lt 3 ]; then
                echo -e "${YELLOW}  ⚠ Retry $attempt/3 - waiting for Cosmos DB lock...${NC}"
                sleep 15
            else
                echo -e "${YELLOW}  ⚠ Could not enable public access (may need manual action in Azure Portal)${NC}"
            fi
        fi
    done

    # Get current user ID
    CURRENT_USER_ID=$(timeout 15 az ad signed-in-user show --query id -o tsv 2>/dev/null || true)

    if [ -z "$CURRENT_USER_ID" ]; then
        echo -e "${YELLOW}  ⚠ Could not get current user ID. Skipping Cosmos DB role assignments.${NC}"
        return 0
    fi

    # Get Cosmos DB account ID
    COSMOS_ACCOUNT_ID=$(timeout 15 az cosmosdb show \
        --name "$COSMOS_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv 2>/dev/null || true)

    if [ -z "$COSMOS_ACCOUNT_ID" ]; then
        echo -e "${YELLOW}  ⚠ Could not get Cosmos DB account ID. Skipping role assignments.${NC}"
        return 0
    fi

    # Assign Cosmos DB Built-in Data Contributor role (allows full data plane access)
    # Role ID: 00000000-0000-0000-0000-000000000002
    echo -e "${YELLOW}  Checking Cosmos DB RBAC role assignments...${NC}"

    # Check if role is already assigned using SQL role assignments
    EXISTING_ROLE=$(timeout 30 az cosmosdb sql role assignment list \
        --account-name "$COSMOS_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?principalId=='$CURRENT_USER_ID'].id" -o tsv 2>/dev/null || true)

    if [ -z "$EXISTING_ROLE" ]; then
        echo -e "${YELLOW}  Assigning Cosmos DB Built-in Data Contributor role...${NC}"

        # Get subscription ID
        SUB_ID=$(timeout 10 az account show --query id -o tsv 2>/dev/null || true)

        # Create SQL role assignment for data access
        timeout 60 az cosmosdb sql role assignment create \
            --account-name "$COSMOS_ACCOUNT" \
            --resource-group "$RESOURCE_GROUP" \
            --role-definition-id "/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.DocumentDB/databaseAccounts/$COSMOS_ACCOUNT/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002" \
            --principal-id "$CURRENT_USER_ID" \
            --scope "/" \
            --output none 2>/dev/null && \
            echo -e "${GREEN}  ✓ Cosmos DB Data Contributor role assigned${NC}" || \
            echo -e "${YELLOW}  ⚠ Could not assign Cosmos DB role (may already exist or require elevated permissions)${NC}"
    else
        echo -e "${GREEN}  ✓ Cosmos DB Data Contributor role already assigned${NC}"
    fi

    echo -e "${GREEN}✓ Cosmos DB configuration complete${NC}"
    echo ""
}

# Run Azure configuration (unless --skip-azure flag is passed)
if [ "$SKIP_AZURE" = true ]; then
    echo -e "${YELLOW}[Azure] Skipping Azure configuration (--skip-azure flag)${NC}"
    echo ""
else
    configure_azure_storage
    configure_cosmos_db
fi

# Check if PostgreSQL container is running (for TrackMan/Redshift testing)
if ! docker ps | grep -q trackman-postgres; then
    echo -e "${YELLOW}Starting PostgreSQL container (for TrackMan testing)...${NC}"
    docker run -d \
        --name trackman-postgres \
        -e POSTGRES_USER=testuser \
        -e POSTGRES_PASSWORD=testpassword \
        -e POSTGRES_DB=trackman_test \
        -p 5432:5432 \
        postgres:14 2>/dev/null || docker start trackman-postgres 2>/dev/null || true
    # Don't wait here - PostgreSQL will be ready by the time we need it
fi

# Kill any existing processes on our ports (in parallel for speed)
echo -e "${YELLOW}Cleaning up existing processes...${NC}"
(lsof -ti:5050 | xargs kill -9 2>/dev/null || true) &
(lsof -ti:5173 | xargs kill -9 2>/dev/null || true) &
(lsof -ti:8501 | xargs kill -9 2>/dev/null || true) &
(lsof -ti:7071 | xargs kill -9 2>/dev/null || true) &
wait

# Export environment variables for TrackMan/Redshift
export USE_REDSHIFT=true
export REDSHIFT_HOST=localhost
export REDSHIFT_PORT=5432
export REDSHIFT_DB=trackman_test
export REDSHIFT_USER=testuser
export REDSHIFT_PASSWORD=testpassword

# Activate virtual environment
source .venv/bin/activate

# Ensure we use the venv's Python explicitly (not shell aliases)
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
VENV_PIP="$SCRIPT_DIR/.venv/bin/pip"

echo ""
echo -e "${BLUE}--- Starting All Services in Parallel ---${NC}"

# Start all services in parallel for faster startup
# Flask backend on port 5050
echo -e "${GREEN}Starting Flask backend on http://localhost:5050${NC}"
cd code
nohup $VENV_PYTHON -m flask run --host=127.0.0.1 --port=5050 > /tmp/flask.log 2>&1 &
FLASK_PID=$!
cd ..

# Vite frontend on port 5173 (start immediately, don't wait for Flask)
echo -e "${GREEN}Starting Vite frontend on http://localhost:5173${NC}"
cd code/frontend
nohup npm run dev > /tmp/vite.log 2>&1 &
VITE_PID=$!
cd ../..

# Start Streamlit Admin UI on port 8501 (parallel)
echo -e "${GREEN}Starting Streamlit Admin UI on http://localhost:8501${NC}"
cd code/backend
nohup $VENV_PYTHON -m streamlit run Admin.py --server.port 8501 --server.headless true > /tmp/streamlit.log 2>&1 &
STREAMLIT_PID=$!
cd ../..

# Start Azure Functions on port 7071 (parallel)
echo -e "${GREEN}Starting Azure Functions on http://localhost:7071${NC}"
cd code/backend/batch
nohup func host start --port 7071 > /tmp/functions.log 2>&1 &
FUNC_PID=$!
cd ../../..

# Wait for all services to start (single combined wait instead of multiple sleeps)
echo ""
echo -e "${YELLOW}Waiting for services to initialize...${NC}"
sleep 5

# Check all services at once
echo -e "${BLUE}--- Service Status ---${NC}"
lsof -i:5050 > /dev/null 2>&1 && echo -e "${GREEN}✓ Flask backend running on port 5050${NC}" || echo -e "${YELLOW}⚠ Flask starting... (check /tmp/flask.log)${NC}"
lsof -i:5173 > /dev/null 2>&1 && echo -e "${GREEN}✓ Vite frontend running on port 5173${NC}" || echo -e "${YELLOW}⚠ Vite starting... (check /tmp/vite.log)${NC}"
lsof -i:8501 > /dev/null 2>&1 && echo -e "${GREEN}✓ Streamlit Admin UI running on port 8501${NC}" || echo -e "${YELLOW}⚠ Streamlit starting... (check /tmp/streamlit.log)${NC}"
lsof -i:7071 > /dev/null 2>&1 && echo -e "${GREEN}✓ Azure Functions running on port 7071${NC}" || echo -e "${YELLOW}⚠ Functions starting... (check /tmp/functions.log)${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Local Environment Ready                         ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC} Chat UI (Frontend):  ${BLUE}http://localhost:5173${NC}                ${GREEN}║${NC}"
echo -e "${GREEN}║${NC} Chat API (Backend):  ${BLUE}http://localhost:5050${NC}                ${GREEN}║${NC}"
echo -e "${GREEN}║${NC} Admin UI:            ${BLUE}http://localhost:8501${NC}                ${GREEN}║${NC}"
echo -e "${GREEN}║${NC} Azure Functions:     ${BLUE}http://localhost:7071${NC}                ${GREEN}║${NC}"
echo -e "${GREEN}║${NC} PostgreSQL:          localhost:5432 (trackman_test)     ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo "  Flask:      tail -f /tmp/flask.log"
echo "  Vite:       tail -f /tmp/vite.log"
echo "  Streamlit:  tail -f /tmp/streamlit.log"
echo "  Functions:  tail -f /tmp/functions.log"
echo ""
echo -e "${YELLOW}To stop all services: ./stop_local.sh${NC}"
echo ""
echo -e "${BLUE}Usage:${NC}"
echo "  • Chat UI: Open http://localhost:5173 to chat with your documents"
echo "  • Admin UI: Open http://localhost:8501 to upload and process documents"
echo "  • TrackMan: Ask database queries like 'Show errors from last 7 days'"
echo "  • /database <query>: Force direct database query (bypasses LLM)"
echo ""
echo -e "${BLUE}Startup Options:${NC}"
echo "  ./start_local.sh              # Full startup (first run, or after updates)"
echo "  ./start_local.sh --skip-azure # Skip Azure policy auto-fix"
echo "  ./start_local.sh --skip-deps  # Skip dependency check (faster)"
echo "  ./start_local.sh --fast       # Skip both Azure + deps (fastest)"
