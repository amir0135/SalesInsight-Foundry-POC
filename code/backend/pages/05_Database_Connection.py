"""
Database Connection Configuration Page

Allows users to configure Snowflake or other database connections
through a user-friendly interface without editing code or .env files.
"""
import logging
import os
import sys
import json
import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from batch.utilities.helpers.env_helper import EnvHelper
from batch.utilities.helpers.azure_blob_storage_client import AzureBlobStorageClient

logger = logging.getLogger(__name__)

# Get parent directory (backend folder)
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Database Connection",
    page_icon=os.path.join(backend_dir, "images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)


def load_css(file_path):
    full_path = os.path.join(backend_dir, file_path)
    with open(full_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("pages/common.css")

# Config file path in blob storage
DB_CONFIG_CONTAINER = "config"
DB_CONFIG_FILENAME = "database_connection.json"

# Default configuration
DEFAULT_CONFIG = {
    "data_source": "local",  # "local", "snowflake", "postgresql"
    "snowflake": {
        "account": "",
        "warehouse": "",
        "database": "",
        "schema": "PUBLIC",
        "user": "",
        "role": "",
    },
    "postgresql": {
        "host": "",
        "port": "5432",
        "database": "",
        "user": "",
        "schema": "public",
    },
    "local": {
        "use_sample_data": True,
        "csv_path": "",
    }
}


LOCAL_CONFIG_PATH = os.path.join(backend_dir, "config", "database_connection.json")


def load_db_config() -> dict:
    """Load database configuration from blob storage or local file."""
    # Try blob storage first (production)
    try:
        blob_client = AzureBlobStorageClient(container_name=DB_CONFIG_CONTAINER)
        blob_data = blob_client.download_file(DB_CONFIG_FILENAME)
        if blob_data:
            return json.loads(blob_data)
    except Exception as e:
        logger.warning(f"Could not load database config from blob storage: {e}")
    
    # Fallback to local file (development)
    try:
        if os.path.exists(LOCAL_CONFIG_PATH):
            with open(LOCAL_CONFIG_PATH, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load local database config: {e}")
    
    return DEFAULT_CONFIG.copy()


def save_db_config(config: dict) -> bool:
    """Save database configuration to blob storage and local file."""
    success = False
    
    # Try blob storage first (production)
    try:
        blob_client = AzureBlobStorageClient(container_name=DB_CONFIG_CONTAINER)
        blob_client.upload_file(
            json.dumps(config, indent=2).encode('utf-8'),
            DB_CONFIG_FILENAME,
            content_type="application/json"
        )
        success = True
        logger.info("Saved database config to blob storage")
    except Exception as e:
        logger.warning(f"Could not save to blob storage: {e}")
    
    # Also save locally (for development and backup)
    try:
        os.makedirs(os.path.dirname(LOCAL_CONFIG_PATH), exist_ok=True)
        with open(LOCAL_CONFIG_PATH, "w") as f:
            json.dump(config, indent=2, fp=f)
        success = True
        logger.info("Saved database config locally")
    except Exception as e:
        logger.warning(f"Could not save config locally: {e}")
        if not success:
            st.error(f"Failed to save configuration: {e}")
    
    return success


def test_snowflake_connection(config: dict) -> tuple[bool, str]:
    """Test Snowflake connection with provided credentials."""
    try:
        import snowflake.connector
        
        conn = snowflake.connector.connect(
            account=config["account"],
            user=config["user"],
            password=st.session_state.get("snowflake_password", ""),
            warehouse=config["warehouse"],
            database=config["database"],
            schema=config["schema"],
            role=config.get("role") or None,
        )
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return True, f"✅ Connected! Warehouse: {result[0]}, Database: {result[1]}, Schema: {result[2]}"
    
    except ImportError:
        return False, "❌ Snowflake connector not installed. Run: pip install snowflake-connector-python"
    except Exception as e:
        return False, f"❌ Connection failed: {str(e)}"


def test_postgresql_connection(config: dict) -> tuple[bool, str]:
    """Test PostgreSQL connection with provided credentials."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=st.session_state.get("postgresql_password", ""),
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT current_database(), current_schema()")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return True, f"✅ Connected! Database: {result[0]}, Schema: {result[1]}"
    
    except ImportError:
        return False, "❌ psycopg2 not installed. Run: pip install psycopg2-binary"
    except Exception as e:
        return False, f"❌ Connection failed: {str(e)}"


def discover_tables(data_source: str, config: dict) -> list[str]:
    """Discover available tables in the connected database."""
    tables = []
    
    try:
        if data_source == "snowflake":
            import snowflake.connector
            conn = snowflake.connector.connect(
                account=config["account"],
                user=config["user"],
                password=st.session_state.get("snowflake_password", ""),
                warehouse=config["warehouse"],
                database=config["database"],
                schema=config["schema"],
            )
            cursor = conn.cursor()
            cursor.execute(f"SHOW TABLES IN SCHEMA {config['database']}.{config['schema']}")
            tables = [row[1] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
        elif data_source == "postgresql":
            import psycopg2
            conn = psycopg2.connect(
                host=config["host"],
                port=config["port"],
                database=config["database"],
                user=config["user"],
                password=st.session_state.get("postgresql_password", ""),
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
            """, (config.get("schema", "public"),))
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
    except Exception as e:
        st.error(f"Failed to discover tables: {e}")
    
    return tables


# Initialize session state
if "db_config" not in st.session_state:
    st.session_state.db_config = load_db_config()

config = st.session_state.db_config

# Page header
st.title("🗄️ Database Connection")
st.markdown("""
Configure your data source for SalesInsight analytics. 
You can use local CSV files for testing or connect to Snowflake/PostgreSQL for production.
""")

# Data source selection
st.markdown("---")
st.subheader("1️⃣ Select Data Source")

data_source = st.radio(
    "Choose your data source:",
    options=["local", "snowflake", "postgresql"],
    format_func=lambda x: {
        "local": "📁 Local Files (CSV/Excel) - For testing & demos",
        "snowflake": "❄️ Snowflake - Production data warehouse",
        "postgresql": "🐘 PostgreSQL - Self-hosted database",
    }[x],
    index=["local", "snowflake", "postgresql"].index(config.get("data_source", "local")),
    help="Select where your sales data is stored"
)

config["data_source"] = data_source

st.markdown("---")

# Configuration based on data source
if data_source == "local":
    st.subheader("2️⃣ Upload CSV Data")
    
    # Detect environment
    env_helper = EnvHelper()
    is_production = os.environ.get("WEBSITE_SITE_NAME") is not None  # Azure App Service sets this
    
    st.markdown("### 📤 Upload CSV File")
    
    if is_production:
        st.info("🌐 **Production Mode**: CSV will be uploaded to Azure Blob Storage")
    else:
        st.info("💻 **Local Mode**: CSV will be saved to the data/ folder")
    
    uploaded_file = st.file_uploader(
        "Upload a CSV file to use as your data source",
        type=["csv"],
        help="Upload a CSV file with headers. Max recommended size: 50MB"
    )
    
    if uploaded_file is not None:
        # Preview the uploaded file
        import pandas as pd
        try:
            df = pd.read_csv(uploaded_file, nrows=5)
            st.write("**Preview (first 5 rows):**")
            st.dataframe(df)
            
            # Show column info
            st.write(f"**Columns ({len(df.columns)}):** {', '.join(df.columns.tolist())}")
            
            # Reset file position for saving
            uploaded_file.seek(0)
            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            st.write(f"**File size:** {file_size_mb:.1f} MB")
            
            # Save button
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("💾 Upload & Save", type="primary"):
                    uploaded_file.seek(0)
                    file_bytes = uploaded_file.getvalue()
                    
                    if is_production:
                        # Upload to Azure Blob Storage
                        try:
                            blob_client = AzureBlobStorageClient(container_name="salesdata")
                            blob_url = blob_client.upload_file(
                                file_bytes,
                                f"csv/{uploaded_file.name}",
                                content_type="text/csv"
                            )
                            st.success(f"✅ Uploaded to Azure Blob Storage!")
                            st.code(f"salesdata/csv/{uploaded_file.name}")
                            
                            # Update config
                            config.setdefault("local", {})["blob_path"] = f"csv/{uploaded_file.name}"
                            config["local"]["uploaded_file"] = uploaded_file.name
                            save_db_config(config)
                            
                            st.info("The app will use this CSV on next restart.")
                        except Exception as e:
                            st.error(f"Upload failed: {e}")
                            logger.exception("Blob upload failed")
                    else:
                        # Save locally
                        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
                        os.makedirs(data_dir, exist_ok=True)
                        
                        file_path = os.path.join(data_dir, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(file_bytes)
                        
                        st.success(f"✅ Saved to `data/{uploaded_file.name}`")
                        
                        # Update config
                        config.setdefault("local", {})["csv_path"] = file_path
                        config["local"]["uploaded_file"] = uploaded_file.name
                        
                    st.info("⚠️ Restart the application to load the new data.")
                    
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
    
    st.markdown("---")
    st.markdown("### 📁 Current Data Files")
    
    if is_production:
        # Show files in blob storage
        try:
            blob_client = AzureBlobStorageClient(container_name="salesdata")
            st.write("**Files in Azure Blob Storage (salesdata/csv/):**")
            # Note: listing blobs would require additional method
            st.write("- Check Azure Portal for uploaded files")
        except Exception as e:
            st.warning(f"Could not list blob files: {e}")
    else:
        # Show existing files in data/ folder
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
        if os.path.isdir(data_dir):
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            if csv_files:
                for f in csv_files:
                    file_path = os.path.join(data_dir, f)
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    
                    # Count rows
                    try:
                        import subprocess
                        result = subprocess.run(['wc', '-l', file_path], capture_output=True, text=True)
                        rows = int(result.stdout.split()[0])
                    except:
                        rows = "?"
                    
                    st.write(f"- **{f}** ({size_mb:.1f} MB, {rows} rows)")
            else:
            st.write("No CSV files found in data/ folder")
    
    st.success("✅ Local mode is ready! CSV files in data/ folder are automatically loaded.")
    
    st.info("""
    **Supported Formats:**
    - CSV files (.csv) - Comma-separated with headers
    - Excel files (.xlsx, .xls) 
    - The filename becomes the table name (cleaned up)
    
    **Your CSV:** `db_more_weu_prod_dbo_OrderHistoryLine.csv` → table `orderhistoryline`
    """)

elif data_source == "snowflake":
    st.subheader("2️⃣ Snowflake Configuration")
    
    st.markdown("""
    Enter your Snowflake connection details below. 
    [📖 Snowflake Setup Guide](https://github.com/amir0135/SalesInsight-Foundry-POC/blob/main/docs/snowflake_setup.md)
    """)
    
    sf_config = config.setdefault("snowflake", DEFAULT_CONFIG["snowflake"].copy())
    
    col1, col2 = st.columns(2)
    
    with col1:
        sf_config["account"] = st.text_input(
            "Account Identifier *",
            value=sf_config.get("account", ""),
            placeholder="xy12345.us-east-1",
            help="Your Snowflake account identifier (e.g., xy12345.us-east-1)"
        )
        
        sf_config["warehouse"] = st.text_input(
            "Warehouse *",
            value=sf_config.get("warehouse", ""),
            placeholder="COMPUTE_WH",
            help="Snowflake warehouse name"
        )
        
        sf_config["database"] = st.text_input(
            "Database *",
            value=sf_config.get("database", ""),
            placeholder="SALES_DB",
            help="Snowflake database name"
        )
    
    with col2:
        sf_config["schema"] = st.text_input(
            "Schema",
            value=sf_config.get("schema", "PUBLIC"),
            placeholder="PUBLIC",
            help="Snowflake schema (default: PUBLIC)"
        )
        
        sf_config["user"] = st.text_input(
            "Username *",
            value=sf_config.get("user", ""),
            placeholder="salesinsight_user",
            help="Snowflake username"
        )
        
        sf_config["role"] = st.text_input(
            "Role (optional)",
            value=sf_config.get("role", ""),
            placeholder="SALESINSIGHT_ROLE",
            help="Snowflake role for access control"
        )
    
    # Password input (not saved to config file for security)
    st.text_input(
        "Password *",
        type="password",
        key="snowflake_password",
        help="Password is used for testing only and NOT saved to configuration"
    )
    
    st.warning("⚠️ **Security Note:** Password is only used for connection testing. In production, use Azure Key Vault.")
    
    # Test connection button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔌 Test Connection", key="test_snowflake"):
            if not sf_config.get("account") or not sf_config.get("user"):
                st.error("Please fill in all required fields (*)")
            elif not st.session_state.get("snowflake_password"):
                st.error("Please enter password to test connection")
            else:
                with st.spinner("Testing connection..."):
                    success, message = test_snowflake_connection(sf_config)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    with col2:
        if st.button("📋 Discover Tables", key="discover_snowflake"):
            if st.session_state.get("snowflake_password"):
                with st.spinner("Discovering tables..."):
                    tables = discover_tables("snowflake", sf_config)
                    if tables:
                        st.session_state.discovered_tables = tables
                    else:
                        st.warning("No tables found or connection failed")
    
    # Show discovered tables
    if st.session_state.get("discovered_tables"):
        st.markdown("**Available Tables:**")
        for table in st.session_state.discovered_tables:
            st.code(table)

elif data_source == "postgresql":
    st.subheader("2️⃣ PostgreSQL Configuration")
    
    pg_config = config.setdefault("postgresql", DEFAULT_CONFIG["postgresql"].copy())
    
    col1, col2 = st.columns(2)
    
    with col1:
        pg_config["host"] = st.text_input(
            "Host *",
            value=pg_config.get("host", ""),
            placeholder="your-server.postgres.database.azure.com",
            help="PostgreSQL server hostname"
        )
        
        pg_config["port"] = st.text_input(
            "Port",
            value=pg_config.get("port", "5432"),
            placeholder="5432",
            help="PostgreSQL port (default: 5432)"
        )
        
        pg_config["database"] = st.text_input(
            "Database *",
            value=pg_config.get("database", ""),
            placeholder="salesdb",
            help="PostgreSQL database name"
        )
    
    with col2:
        pg_config["schema"] = st.text_input(
            "Schema",
            value=pg_config.get("schema", "public"),
            placeholder="public",
            help="PostgreSQL schema (default: public)"
        )
        
        pg_config["user"] = st.text_input(
            "Username *",
            value=pg_config.get("user", ""),
            placeholder="postgres",
            help="PostgreSQL username"
        )
    
    st.text_input(
        "Password *",
        type="password",
        key="postgresql_password",
        help="Password is used for testing only and NOT saved"
    )
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔌 Test Connection", key="test_pg"):
            if not pg_config.get("host") or not pg_config.get("user"):
                st.error("Please fill in all required fields (*)")
            elif not st.session_state.get("postgresql_password"):
                st.error("Please enter password to test connection")
            else:
                with st.spinner("Testing connection..."):
                    success, message = test_postgresql_connection(pg_config)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    with col2:
        if st.button("📋 Discover Tables", key="discover_pg"):
            if st.session_state.get("postgresql_password"):
                with st.spinner("Discovering tables..."):
                    tables = discover_tables("postgresql", pg_config)
                    if tables:
                        st.session_state.discovered_tables = tables

# Save configuration
st.markdown("---")
st.subheader("3️⃣ Save Configuration")

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("💾 Save Configuration", type="primary"):
        st.session_state.db_config = config
        if save_db_config(config):
            st.success("✅ Configuration saved successfully!")
            st.info("Restart the application for changes to take effect.")
        else:
            st.error("Failed to save configuration")

with col2:
    if st.button("🔄 Reset to Defaults"):
        st.session_state.db_config = DEFAULT_CONFIG.copy()
        config = st.session_state.db_config
        st.success("Configuration reset to defaults")
        st.rerun()

# Show current configuration (without sensitive data)
with st.expander("📄 View Current Configuration"):
    display_config = config.copy()
    # Remove any sensitive fields
    if "password" in display_config.get("snowflake", {}):
        display_config["snowflake"]["password"] = "***hidden***"
    if "password" in display_config.get("postgresql", {}):
        display_config["postgresql"]["password"] = "***hidden***"
    st.json(display_config)

# Help section
st.markdown("---")
st.subheader("❓ Need Help?")

with st.expander("How do I get my Snowflake account identifier?"):
    st.markdown("""
    Your Snowflake account identifier is shown in your Snowflake URL:
    - `https://xy12345.us-east-1.snowflakecomputing.com` → Account: `xy12345.us-east-1`
    - `https://myorg-myaccount.snowflakecomputing.com` → Account: `myorg-myaccount`
    
    You can also find it in Snowflake:
    1. Click your name (bottom left)
    2. Go to "Account" 
    3. Copy the "Account Identifier"
    """)

with st.expander("How do I set up the ORDERHISTORYLINE table in Snowflake?"):
    st.markdown("""
    Run this SQL in Snowflake to create the table:
    
    ```sql
    CREATE TABLE IF NOT EXISTS ORDERHISTORYLINE (
        Id VARCHAR(50) PRIMARY KEY,
        DomainId VARCHAR(200),
        OrderHistoryId VARCHAR(50),
        Ean VARCHAR(50),
        SoftDeleted BOOLEAN,
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
    ```
    
    Then load your CSV data using:
    ```sql
    COPY INTO ORDERHISTORYLINE
    FROM @your_stage/your_file.csv
    FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1);
    ```
    """)

with st.expander("How do I securely store credentials in production?"):
    st.markdown("""
    **For production, use Azure Key Vault:**
    
    1. Store your credentials in Key Vault:
    ```bash
    az keyvault secret set --vault-name your-keyvault \\
      --name SNOWFLAKE-PASSWORD --value "your-password"
    ```
    
    2. The app will automatically fetch from Key Vault when `AZURE_AUTH_TYPE=rbac`
    
    3. Grant the App Service identity access to Key Vault:
    ```bash
    az keyvault set-policy --name your-keyvault \\
      --object-id <app-service-identity-id> \\
      --secret-permissions get list
    ```
    """)
