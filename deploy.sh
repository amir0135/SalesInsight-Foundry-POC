#!/bin/bash
# Container Deploy - builds in Azure ACR, then updates App Services
# Usage: ./deploy.sh [web|admin|function|all]
#   web      - Deploy web frontend only (default)
#   admin    - Deploy admin UI only
#   function - Deploy backend function only
#   all      - Deploy all three services

set -e

RESOURCE_GROUP="trackman-chatwithdata-POC"
ACR_NAME="acrcwydbjw4t"
WEB_APP_NAME="app-cwydbjw4t"
ADMIN_APP_NAME="app-cwydbjw4t-admin"
FUNCTION_APP_NAME="func-cwydbjw4t-docker"
IMAGE_TAG=$(date +%Y%m%d%H%M%S)
TARGET="${1:-web}"

cd "$(dirname "$0")"

deploy_container_service() {
    local service="$1"
    local image_name="$2"
    local dockerfile="$3"
    local app_name="$4"
    local app_type="${5:-webapp}"  # webapp or functionapp

    echo ""
    echo "→ Building $service container in Azure..."
    az acr build \
        --registry "$ACR_NAME" \
        --image "$image_name:$IMAGE_TAG" \
        --image "$image_name:latest" \
        -f "$dockerfile" \
        . \
        --only-show-errors

    echo "→ Updating $service App Service..."
    if [ "$app_type" = "webapp" ]; then
        az webapp config container set \
            --name "$app_name" \
            --resource-group "$RESOURCE_GROUP" \
            --container-image-name "$ACR_NAME.azurecr.io/$image_name:$IMAGE_TAG" \
            --output none
        az webapp restart --name "$app_name" --resource-group "$RESOURCE_GROUP" --output none
    else
        az functionapp config container set \
            --name "$app_name" \
            --resource-group "$RESOURCE_GROUP" \
            --image "$ACR_NAME.azurecr.io/$image_name:$IMAGE_TAG" \
            --output none
        az functionapp restart --name "$app_name" --resource-group "$RESOURCE_GROUP" --output none
    fi
    echo "  $service deployed -> https://$app_name.azurewebsites.net"
}

deploy_admin() {
    echo ""
    echo "→ Deploying admin (code-based) via zip deploy..."
    local tmpdir
    tmpdir=$(mktemp -d)
    # Package the admin app code
    cp -r code/backend/* "$tmpdir/"
    cp -r code/backend/batch/utilities "$tmpdir/" 2>/dev/null || true
    cd "$tmpdir"
    zip -r "$tmpdir/admin.zip" . -x '__pycache__/*' '*.pyc' > /dev/null
    cd - > /dev/null
    az webapp deploy \
        --name "$ADMIN_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --src-path "$tmpdir/admin.zip" \
        --type zip \
        --output none
    rm -rf "$tmpdir"
    echo "  admin deployed -> https://$ADMIN_APP_NAME.azurewebsites.net"
}

echo "Container Deploy [$TARGET]"
echo "========================================"
START_TIME=$(date +%s)

case "$TARGET" in
    web)
        deploy_container_service "web" "rag-webapp" "docker/Frontend.Dockerfile" "$WEB_APP_NAME" "webapp"
        ;;
    admin)
        deploy_admin
        ;;
    function)
        deploy_container_service "function" "rag-backend" "docker/Backend.Dockerfile" "$FUNCTION_APP_NAME" "functionapp"
        ;;
    all)
        deploy_container_service "web" "rag-webapp" "docker/Frontend.Dockerfile" "$WEB_APP_NAME" "webapp"
        deploy_admin
        deploy_container_service "function" "rag-backend" "docker/Backend.Dockerfile" "$FUNCTION_APP_NAME" "functionapp"
        ;;
    *)
        echo "Usage: $0 [web|admin|function|all]"
        exit 1
        ;;
esac

END_TIME=$(date +%s)
echo ""
echo "========================================"
echo "Deployed in $((END_TIME - START_TIME))s"
