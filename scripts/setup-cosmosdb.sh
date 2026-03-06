#!/bin/bash
# ============================================================================
# Lab 1a: Setup Azure Cosmos DB with Vector Search
# ============================================================================
# This script creates a serverless Cosmos DB account optimized for the lab demo.
# Estimated cost: $1-5/month for light usage
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Lab 1a: Azure Cosmos DB Vector Store Setup           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Configuration - Override these with environment variables if needed
# ============================================================================
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-agent-labs}"
LOCATION="${LOCATION:-westus2}"
COSMOS_ACCOUNT="${COSMOS_ACCOUNT:-cosmos-sre-agent-$RANDOM}"
DATABASE_NAME="${DATABASE_NAME:-sre-data}"
CONTAINER_NAME="${CONTAINER_NAME:-sre-knowledge}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/../infra"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Resource Group:  $RESOURCE_GROUP"
echo "  Location:        $LOCATION"
echo "  Cosmos Account:  $COSMOS_ACCOUNT"
echo "  Database:        $DATABASE_NAME"
echo "  Container:       $CONTAINER_NAME"
echo ""

# ============================================================================
# Pre-flight checks
# ============================================================================
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI is not installed.${NC}"
    echo "Install from: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Not logged in to Azure. Running 'az login'...${NC}"
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
echo -e "${GREEN}✓ Logged in to Azure${NC}"
echo "  Subscription: $SUBSCRIPTION"
echo ""

# ============================================================================
# Create Resource Group
# ============================================================================
echo -e "${YELLOW}Step 1/4: Creating resource group...${NC}"

if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${GREEN}✓ Resource group '$RESOURCE_GROUP' already exists${NC}"
else
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    echo -e "${GREEN}✓ Created resource group '$RESOURCE_GROUP'${NC}"
fi
echo ""

# ============================================================================
# Create Cosmos DB Account (Serverless)
# ============================================================================
echo -e "${YELLOW}Step 2/4: Creating Cosmos DB account (this takes 2-3 minutes)...${NC}"

if az cosmosdb show --name "$COSMOS_ACCOUNT" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${GREEN}✓ Cosmos DB account '$COSMOS_ACCOUNT' already exists${NC}"
else
    az cosmosdb create \
        --name "$COSMOS_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --locations regionName="$LOCATION" \
        --capacity-mode Serverless \
        --capabilities EnableNoSQLVectorSearch \
        --default-consistency-level Session \
        --output none
    echo -e "${GREEN}✓ Created Cosmos DB account '$COSMOS_ACCOUNT'${NC}"
fi

# Get the endpoint
COSMOS_ENDPOINT=$(az cosmosdb show \
    --name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query documentEndpoint -o tsv)
echo "  Endpoint: $COSMOS_ENDPOINT"
echo ""

# ============================================================================
# Create Database
# ============================================================================
echo -e "${YELLOW}Step 3/4: Creating database...${NC}"

if az cosmosdb sql database show \
    --account-name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$DATABASE_NAME" &> /dev/null; then
    echo -e "${GREEN}✓ Database '$DATABASE_NAME' already exists${NC}"
else
    az cosmosdb sql database create \
        --account-name "$COSMOS_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DATABASE_NAME" \
        --output none
    echo -e "${GREEN}✓ Created database '$DATABASE_NAME'${NC}"
fi
echo ""

# ============================================================================
# Create Container with Vector Index
# ============================================================================
echo -e "${YELLOW}Step 4/4: Creating container with vector index...${NC}"

if az cosmosdb sql container show \
    --account-name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --database-name "$DATABASE_NAME" \
    --name "$CONTAINER_NAME" &> /dev/null; then
    echo -e "${GREEN}✓ Container '$CONTAINER_NAME' already exists${NC}"
else
    # Use REST API to create container with vector embedding policy
    # The CLI doesn't support --vector-embedding-policy yet
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    
    az rest --method PUT \
        --uri "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.DocumentDB/databaseAccounts/${COSMOS_ACCOUNT}/sqlDatabases/${DATABASE_NAME}/containers/${CONTAINER_NAME}?api-version=2024-05-15" \
        --body "{
            \"properties\": {
                \"resource\": {
                    \"id\": \"${CONTAINER_NAME}\",
                    \"partitionKey\": {
                        \"paths\": [\"/category\"],
                        \"kind\": \"Hash\"
                    },
                    \"indexingPolicy\": $(cat "$INFRA_DIR/vector-index-policy.json"),
                    \"vectorEmbeddingPolicy\": $(cat "$INFRA_DIR/vector-embedding-policy.json")
                }
            }
        }" \
        --output none
    
    echo -e "${GREEN}✓ Created container '$CONTAINER_NAME' with vector index${NC}"
fi
echo ""

# ============================================================================
# Assign RBAC (Data Contributor role for current user)
# ============================================================================
echo -e "${YELLOW}Assigning RBAC permissions...${NC}"

CURRENT_USER_ID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")
if [ -n "$CURRENT_USER_ID" ]; then
    # Cosmos DB Built-in Data Contributor role
    ROLE_ID="00000000-0000-0000-0000-000000000002"
    
    az cosmosdb sql role assignment create \
        --account-name "$COSMOS_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --principal-id "$CURRENT_USER_ID" \
        --role-definition-id "$ROLE_ID" \
        --scope "/" \
        --output none 2>/dev/null || true
    
    echo -e "${GREEN}✓ RBAC role assigned${NC}"
else
    echo -e "${YELLOW}⚠ Could not determine current user ID - RBAC assignment skipped${NC}"
    echo "  You may need to assign the 'Cosmos DB Built-in Data Contributor' role manually."
fi
echo ""

# ============================================================================
# Output Summary
# ============================================================================
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Setup Complete!                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Add these to your .env file:${NC}"
echo ""
echo "# Cosmos DB Configuration (Lab 1a)"
echo "COSMOS_ENDPOINT=$COSMOS_ENDPOINT"
echo "COSMOS_DATABASE=$DATABASE_NAME"
echo "COSMOS_CONTAINER=$CONTAINER_NAME"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Copy the environment variables above to your .env file"
echo "2. Run: python scripts/load_knowledge_base.py"
echo "3. Open lab1a-cosmosdb-vector-store.ipynb"
echo ""
echo -e "${YELLOW}Estimated cost:${NC} \$1-5/month for demo usage (serverless)"
echo ""
echo -e "${YELLOW}To clean up when done:${NC}"
echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
echo ""
