#!/bin/bash
# Container Deploy - ~2 minutes
# Builds in Azure ACR (fast), then updates App Service
# Usage: ./deploy.sh

set -e

RESOURCE_GROUP="trackman-chatwithdata-POC"
ACR_NAME="acrcwydbjw4t"
APP_NAME="app-cwydbjw4t"
IMAGE_TAG=$(date +%Y%m%d%H%M%S)

echo "🐳 Container Deploy"
echo "════════════════════════════════════════"

cd "$(dirname "$0")/.."
START_TIME=$(date +%s)

# Build in ACR (faster than local build + push)
echo "→ Building container in Azure..."
az acr build \
    --registry "$ACR_NAME" \
    --image chat-web:$IMAGE_TAG \
    --image chat-web:latest \
    -f docker/Frontend.Dockerfile \
    . \
    --only-show-errors

# Update App Service to use new image
echo "→ Updating App Service..."
az webapp config container set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --container-image-name "$ACR_NAME.azurecr.io/chat-web:$IMAGE_TAG" \
    --output none

# Restart to pick up new image
az webapp restart --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --output none

END_TIME=$(date +%s)
echo ""
echo "════════════════════════════════════════"
echo "✅ Deployed in $((END_TIME - START_TIME))s"
echo "🌐 https://$APP_NAME.azurewebsites.net"
