#!/bin/bash

pip install --upgrade pip

pip install --upgrade poetry

# https://pypi.org/project/poetry-plugin-export/
pip install --upgrade poetry-plugin-export

poetry env use python3.11

poetry config warnings.export false

poetry install --with dev

poetry run pre-commit install

(cd ./code/frontend; npm install)

(cd ./tests/integration/ui; npm install)

# =============================================================================
# Generate .env from GitHub Codespaces secrets (if running in Codespaces)
# =============================================================================
# When launching via the "Open in Codespaces" button, users can pre-configure
# secrets in their repo/org settings. This block writes them to .env so the
# app can pick them up.
#
# Required Codespaces secrets:
#   SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
#   AZURE_OPENAI_RESOURCE, AZURE_OPENAI_API_KEY
#
# Optional:
#   SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA, SNOWFLAKE_ROLE,
#   AZURE_OPENAI_MODEL, AZURE_SEARCH_SERVICE, AZURE_SEARCH_KEY,
#   AZURE_SEARCH_INDEX, AZURE_BLOB_ACCOUNT_NAME, AZURE_BLOB_ACCOUNT_KEY

if [ "$CODESPACES" = "true" ] && [ ! -f .env ]; then
    echo "Running in GitHub Codespaces — generating .env from secrets..."

    cat > .env << 'HEADER'
# Auto-generated in GitHub Codespaces from repository secrets.
# Edit this file or add secrets in GitHub Settings > Codespaces > Secrets.
HEADER

    # Write each known env var if it's set
    ENV_VARS=(
        SNOWFLAKE_ACCOUNT SNOWFLAKE_USER SNOWFLAKE_PASSWORD
        SNOWFLAKE_WAREHOUSE SNOWFLAKE_DATABASE SNOWFLAKE_SCHEMA SNOWFLAKE_ROLE
        AZURE_OPENAI_RESOURCE AZURE_OPENAI_API_KEY
        AZURE_OPENAI_MODEL AZURE_OPENAI_MODEL_NAME
        AZURE_SEARCH_SERVICE AZURE_SEARCH_KEY AZURE_SEARCH_INDEX
        AZURE_BLOB_ACCOUNT_NAME AZURE_BLOB_ACCOUNT_KEY AZURE_BLOB_CONTAINER_NAME
        AZURE_AUTH_TYPE
    )

    for var in "${ENV_VARS[@]}"; do
        val="${!var}"
        if [ -n "$val" ]; then
            echo "${var}=${val}" >> .env
        fi
    done

    # Ensure defaults for vars that may not have been set as secrets
    grep -q "^SALESINSIGHT_USE_LOCAL_DATA=" .env 2>/dev/null || echo "SALESINSIGHT_USE_LOCAL_DATA=false" >> .env
    grep -q "^AZURE_OPENAI_MODEL=" .env 2>/dev/null || echo "AZURE_OPENAI_MODEL=gpt-4o" >> .env
    grep -q "^AZURE_OPENAI_MODEL_NAME=" .env 2>/dev/null || echo "AZURE_OPENAI_MODEL_NAME=gpt-4o" >> .env
    grep -q "^AZURE_OPENAI_TEMPERATURE=" .env 2>/dev/null || echo "AZURE_OPENAI_TEMPERATURE=0" >> .env
    grep -q "^AZURE_OPENAI_MAX_TOKENS=" .env 2>/dev/null || echo "AZURE_OPENAI_MAX_TOKENS=1000" >> .env
    grep -q "^AZURE_OPENAI_API_VERSION=" .env 2>/dev/null || echo "AZURE_OPENAI_API_VERSION=2024-02-01" >> .env
    grep -q "^AZURE_OPENAI_STREAM=" .env 2>/dev/null || echo "AZURE_OPENAI_STREAM=True" >> .env
    grep -q "^AZURE_AUTH_TYPE=" .env 2>/dev/null || echo "AZURE_AUTH_TYPE=keys" >> .env
    grep -q "^ORCHESTRATION_STRATEGY=" .env 2>/dev/null || echo "ORCHESTRATION_STRATEGY=openai_function" >> .env
    grep -q "^CONVERSATION_FLOW=" .env 2>/dev/null || echo "CONVERSATION_FLOW=custom" >> .env
    grep -q "^BACKEND_URL=" .env 2>/dev/null || echo "BACKEND_URL=http://localhost:7071" >> .env
    grep -q "^LOGLEVEL=" .env 2>/dev/null || echo "LOGLEVEL=INFO" >> .env

    echo "✓ .env generated from Codespaces secrets"

    # Check if key secrets are missing and warn
    MISSING=""
    [ -z "$SNOWFLAKE_ACCOUNT" ] && MISSING="$MISSING SNOWFLAKE_ACCOUNT"
    [ -z "$AZURE_OPENAI_RESOURCE" ] && MISSING="$MISSING AZURE_OPENAI_RESOURCE"
    [ -z "$AZURE_OPENAI_API_KEY" ] && MISSING="$MISSING AZURE_OPENAI_API_KEY"

    if [ -n "$MISSING" ]; then
        echo ""
        echo "⚠ Missing Codespaces secrets:$MISSING"
        echo "  Add them at: GitHub repo → Settings → Secrets → Codespaces"
        echo "  Or edit .env manually, then run: ./scripts/quickstart_snowflake.sh"
        echo ""
    fi
elif [ ! -f .env ]; then
    echo "No .env found. Run: cp .env.example .env and fill in your credentials."
    echo "Or run: ./scripts/quickstart_snowflake.sh for an interactive setup."
fi
