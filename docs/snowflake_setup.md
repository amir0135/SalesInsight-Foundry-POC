# Snowflake Setup Guide for SalesInsight

This guide helps you connect SalesInsight to your Snowflake data warehouse.

## Quick Start (5 minutes)

### 1. Create the Table in Snowflake

Run this SQL in your Snowflake worksheet:

```sql
-- Create database and schema (if needed)
CREATE DATABASE IF NOT EXISTS SALES_DB;
USE DATABASE SALES_DB;
CREATE SCHEMA IF NOT EXISTS ORDERS;
USE SCHEMA ORDERS;

-- Create the OrderHistoryLine table
CREATE TABLE IF NOT EXISTS ORDERHISTORYLINE (
    Id VARCHAR(50) PRIMARY KEY,
    DomainId VARCHAR(200),
    OrderHistoryId VARCHAR(50),
    Ean VARCHAR(50),
    SoftDeleted BOOLEAN DEFAULT FALSE,
    OrderType VARCHAR(50),
    RequestedDeliveryDate TIMESTAMP_NTZ,
    ConfirmedDeliveryDate TIMESTAMP_NTZ,
    RequestQuantity INTEGER,
    RequestQuantityPieces INTEGER,
    ConfirmedDeliveryQuantity INTEGER,
    ConfirmedDeliveryQuantityPieces INTEGER,
    CurrencyIsoAlpha3 VARCHAR(10),
    UnitRetailPrice DECIMAL(10,2),
    UnitGrossPrice DECIMAL(10,2),
    UnitNetPrice DECIMAL(10,2),
    StyleNumber VARCHAR(50),
    Status VARCHAR(50),
    SkuType VARCHAR(50),
    Discount DECIMAL(5,2),
    EstimatedDeliveryDate TIMESTAMP_NTZ,
    BrandId VARCHAR(50),
    ProductLineId VARCHAR(50),
    Note TEXT
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_orderhistory_style ON ORDERHISTORYLINE(StyleNumber);
CREATE INDEX IF NOT EXISTS idx_orderhistory_status ON ORDERHISTORYLINE(Status);
CREATE INDEX IF NOT EXISTS idx_orderhistory_brand ON ORDERHISTORYLINE(BrandId);
CREATE INDEX IF NOT EXISTS idx_orderhistory_currency ON ORDERHISTORYLINE(CurrencyIsoAlpha3);
```

### 2. Load Your Data

**Option A: Upload CSV via Snowflake UI**
1. Go to Snowflake → Data → Databases → SALES_DB → ORDERS → ORDERHISTORYLINE
2. Click "Load Data"
3. Upload your CSV file
4. Map columns automatically

**Option B: Load from S3/Azure Blob**
```sql
-- Create a stage pointing to your storage
CREATE STAGE my_stage
  URL = 's3://your-bucket/data/'
  CREDENTIALS = (AWS_KEY_ID='...' AWS_SECRET_KEY='...');

-- Or for Azure Blob:
CREATE STAGE my_azure_stage
  URL = 'azure://youraccount.blob.core.windows.net/container'
  CREDENTIALS = (AZURE_SAS_TOKEN='...');

-- Load the data
COPY INTO ORDERHISTORYLINE
FROM @my_stage/db_more_weu_prod_dbo_OrderHistoryLine.csv
FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);
```

**Option C: Use Snowflake's COPY command with local file**
```sql
-- First upload to a stage
PUT file:///path/to/db_more_weu_prod_dbo_OrderHistoryLine.csv @~;

-- Then copy into table
COPY INTO ORDERHISTORYLINE
FROM @~/db_more_weu_prod_dbo_OrderHistoryLine.csv
FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);
```

### 3. Configure Environment Variables

Add these to your `.env` file or Azure App Service settings:

```bash
# Disable local mode to use Snowflake
SALESINSIGHT_USE_LOCAL_DATA=false

# Snowflake connection
SNOWFLAKE_ACCOUNT=xy12345.us-east-1     # Your account identifier
SNOWFLAKE_USER=salesinsight_user         # Service account recommended
SNOWFLAKE_PASSWORD=<from-key-vault>      # Use Key Vault in production!
SNOWFLAKE_WAREHOUSE=COMPUTE_WH           # Your warehouse name
SNOWFLAKE_DATABASE=SALES_DB              # Database name
SNOWFLAKE_SCHEMA=ORDERS                  # Schema name
SNOWFLAKE_ROLE=SALESINSIGHT_ROLE         # Optional: specific role
```

### 4. Create a Service User (Recommended)

```sql
-- Create a dedicated role and user for SalesInsight
CREATE ROLE SALESINSIGHT_ROLE;
CREATE USER SALESINSIGHT_USER
  PASSWORD = 'your-secure-password'
  DEFAULT_ROLE = SALESINSIGHT_ROLE
  DEFAULT_WAREHOUSE = COMPUTE_WH;

-- Grant permissions (READ ONLY for security)
GRANT USAGE ON DATABASE SALES_DB TO ROLE SALESINSIGHT_ROLE;
GRANT USAGE ON SCHEMA SALES_DB.ORDERS TO ROLE SALESINSIGHT_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA SALES_DB.ORDERS TO ROLE SALESINSIGHT_ROLE;
GRANT ROLE SALESINSIGHT_ROLE TO USER SALESINSIGHT_USER;
```

## Security Best Practices

### Use Azure Key Vault for Credentials

Instead of storing passwords in environment variables:

```bash
# Store in Key Vault
az keyvault secret set --vault-name your-keyvault \
  --name SNOWFLAKE-PASSWORD \
  --value "your-secure-password"

# Reference in .env
SNOWFLAKE_PASSWORD_SECRET_NAME=SNOWFLAKE-PASSWORD
```

The app will automatically fetch from Key Vault when `AZURE_AUTH_TYPE=rbac`.

### IP Allowlisting

In Snowflake, restrict access to your Azure App Service IPs:
1. Go to Admin → Security → Network Policies
2. Add your Azure App Service outbound IPs

### Use Key-Pair Authentication (Most Secure)

```sql
-- In Snowflake
ALTER USER SALESINSIGHT_USER SET RSA_PUBLIC_KEY='MIIBIjANBgkqh...';
```

```python
# In code - already supported
SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/rsa_key.p8
```

## Verify Connection

Test your connection locally:

```bash
# Set environment variables
export SALESINSIGHT_USE_LOCAL_DATA=false
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=salesinsight_user
export SNOWFLAKE_PASSWORD=your-password
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH
export SNOWFLAKE_DATABASE=SALES_DB
export SNOWFLAKE_SCHEMA=ORDERS

# Run the test script
python scripts/test_salesinsight_local.py
```

## Troubleshooting

### "Account not found"
- Check your account identifier format: `account.region` (e.g., `xy12345.us-east-1`)
- For Azure-hosted Snowflake: `account.azure-region.azure`

### "Warehouse does not exist"
- Verify warehouse name and that it's started
- Check your user has USAGE permission on the warehouse

### "Table not found"
- Ensure database and schema are correct
- Run: `SHOW TABLES IN SCHEMA SALES_DB.ORDERS;`

### Query timeout
- Increase warehouse size temporarily
- Check for missing indexes on filtered columns

## Performance Tips

1. **Use appropriate warehouse size**: Start with XSMALL for testing, scale up for production
2. **Add clustering keys** for large tables:
   ```sql
   ALTER TABLE ORDERHISTORYLINE CLUSTER BY (Status, BrandId);
   ```
3. **Create materialized views** for common aggregations
4. **Enable query caching**: Already on by default in Snowflake
