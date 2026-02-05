"""
Local SQLite Data Source for testing SalesInsight without Snowflake.

This module provides a SQLite-based data source that can load multiple file formats
(CSV, XLSX, PDF tables) for local development and testing.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .base_data_source import BaseDataSource, ColumnSchema, QueryResult, TableSchema

logger = logging.getLogger(__name__)


class SQLiteDataSource(BaseDataSource):
    """
    SQLite-based data source for local testing.

    This data source loads multiple file formats into an in-memory SQLite database,
    allowing local testing of NL2SQL queries without Snowflake.
    
    Supported formats:
    - CSV files (.csv)
    - Excel files (.xlsx, .xls)
    - PDF tables (.pdf) - requires Azure Document Intelligence
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        csv_files: Optional[Dict[str, str]] = None,
        data_files: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize SQLite data source.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory
            csv_files: Dict mapping table names to CSV file paths (legacy)
            data_files: Dict mapping table names to file paths (CSV, XLSX, PDF)
        """
        self._db_path = db_path
        # Merge csv_files into data_files for backward compatibility
        self._data_files = data_files or {}
        if csv_files:
            self._data_files.update(csv_files)
        self._connection: Optional[sqlite3.Connection] = None
        self._schema_cache: Dict[str, TableSchema] = {}

    @classmethod
    def from_csv(cls, csv_path: str, table_name: str = "data") -> "SQLiteDataSource":
        """
        Create a SQLiteDataSource from a single CSV file.

        Args:
            csv_path: Path to the CSV file
            table_name: Name of the table to create

        Returns:
            Configured SQLiteDataSource instance
        """
        instance = cls(
            db_path=":memory:",
            data_files={table_name: csv_path}
        )
        return instance

    @classmethod
    def from_excel(cls, excel_path: str, table_name: str = "data", sheet_name: Union[str, int] = 0) -> "SQLiteDataSource":
        """
        Create a SQLiteDataSource from an Excel file.

        Args:
            excel_path: Path to the Excel file
            table_name: Name of the table to create
            sheet_name: Sheet name or index to read

        Returns:
            Configured SQLiteDataSource instance
        """
        instance = cls(db_path=":memory:")
        instance._excel_config = {table_name: {"path": excel_path, "sheet": sheet_name}}
        instance._data_files[table_name] = excel_path
        return instance

    @classmethod
    def from_files(cls, files: Dict[str, str]) -> "SQLiteDataSource":
        """
        Create a SQLiteDataSource from multiple files of various formats.
        
        File type is detected from extension (.csv, .xlsx, .xls, .pdf).

        Args:
            files: Dict mapping table names to file paths

        Returns:
            Configured SQLiteDataSource instance
            
        Example:
            ds = SQLiteDataSource.from_files({
                "orders": "data/orders.csv",
                "products": "data/products.xlsx",
                "sellout_report": "data/customer_sellout.pdf"
            })
        """
        return cls(db_path=":memory:", data_files=files)

    @classmethod
    def from_dataframes(cls, dataframes: Dict[str, pd.DataFrame]) -> "SQLiteDataSource":
        """
        Create a SQLiteDataSource from pandas DataFrames directly.

        Args:
            dataframes: Dict mapping table names to DataFrames

        Returns:
            Configured SQLiteDataSource instance
        """
        instance = cls(db_path=":memory:")
        instance._preloaded_dataframes = dataframes
        return instance

    def connect(self) -> None:
        """Connect to SQLite database and load data files."""
        if self._connection is not None:
            return

        logger.info("Connecting to SQLite database: %s", self._db_path)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row

        # Load preloaded DataFrames first (if any)
        if hasattr(self, '_preloaded_dataframes'):
            for table_name, df in self._preloaded_dataframes.items():
                self._load_dataframe_to_table(table_name, df)

        # Load data files based on extension
        for table_name, file_path in self._data_files.items():
            self._load_file_to_table(table_name, file_path)

        logger.info("SQLite connection established with %d tables", len(self._schema_cache))

    def _load_file_to_table(self, table_name: str, file_path: str) -> None:
        """Load a file into a SQLite table based on its extension."""
        path = Path(file_path)
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return

        extension = path.suffix.lower()
        
        if extension == '.csv':
            self._load_csv_to_table(table_name, file_path)
        elif extension in ('.xlsx', '.xls'):
            self._load_excel_to_table(table_name, file_path)
        elif extension == '.pdf':
            self._load_pdf_to_table(table_name, file_path)
        else:
            logger.warning("Unsupported file format: %s", extension)

    def _load_csv_to_table(self, table_name: str, csv_path: str) -> None:
        """Load a CSV file into a SQLite table."""
        logger.info("Loading CSV %s from %s", table_name, csv_path)

        try:
            # Read CSV with pandas
            df = pd.read_csv(csv_path, low_memory=False)
            self._load_dataframe_to_table(table_name, df)
        except Exception as e:
            logger.error("Failed to load CSV %s: %s", csv_path, e)
            raise

    def _load_excel_to_table(self, table_name: str, excel_path: str) -> None:
        """Load an Excel file into a SQLite table."""
        logger.info("Loading Excel %s from %s", table_name, excel_path)

        try:
            # Check for specific sheet configuration
            sheet_name = 0
            if hasattr(self, '_excel_config') and table_name in self._excel_config:
                sheet_name = self._excel_config[table_name].get('sheet', 0)

            # Read Excel with pandas
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            self._load_dataframe_to_table(table_name, df)
        except Exception as e:
            logger.error("Failed to load Excel %s: %s", excel_path, e)
            raise

    def _load_pdf_to_table(self, table_name: str, pdf_path: str) -> None:
        """
        Load tables from a PDF file into SQLite.
        
        Uses Azure Document Intelligence to extract tables from PDFs.
        Falls back to simple table extraction if Azure is not configured.
        """
        logger.info("Loading PDF %s from %s", table_name, pdf_path)

        try:
            # Try Azure Document Intelligence first
            df = self._extract_tables_from_pdf_azure(pdf_path)
            if df is not None and not df.empty:
                self._load_dataframe_to_table(table_name, df)
                return
        except Exception as e:
            logger.warning("Azure PDF extraction failed: %s. Trying fallback.", e)

        try:
            # Fallback: try tabula-py or camelot if available
            df = self._extract_tables_from_pdf_fallback(pdf_path)
            if df is not None and not df.empty:
                self._load_dataframe_to_table(table_name, df)
            else:
                logger.warning("No tables found in PDF: %s", pdf_path)
        except Exception as e:
            logger.error("Failed to extract tables from PDF %s: %s", pdf_path, e)
            raise

    def _extract_tables_from_pdf_azure(self, pdf_path: str) -> Optional[pd.DataFrame]:
        """Extract tables from PDF using Azure Document Intelligence."""
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.identity import DefaultAzureCredential
            from ..helpers.env_helper import EnvHelper
            
            env = EnvHelper()
            endpoint = env.AZURE_FORM_RECOGNIZER_ENDPOINT
            
            if not endpoint:
                logger.info("Azure Form Recognizer not configured")
                return None
            
            credential = DefaultAzureCredential()
            client = DocumentAnalysisClient(endpoint=endpoint, credential=credential)
            
            with open(pdf_path, "rb") as f:
                poller = client.begin_analyze_document("prebuilt-layout", f)
                result = poller.result()
            
            # Extract all tables and combine them
            all_tables = []
            for table in result.tables:
                # Convert table to DataFrame
                rows = {}
                for cell in table.cells:
                    row_idx = cell.row_index
                    col_idx = cell.column_index
                    if row_idx not in rows:
                        rows[row_idx] = {}
                    rows[row_idx][col_idx] = cell.content
                
                if rows:
                    # First row as header
                    headers = [rows.get(0, {}).get(i, f"col_{i}") for i in range(table.column_count)]
                    data = []
                    for row_idx in range(1, table.row_count):
                        row_data = [rows.get(row_idx, {}).get(i, "") for i in range(table.column_count)]
                        data.append(row_data)
                    
                    df = pd.DataFrame(data, columns=headers)
                    all_tables.append(df)
            
            if all_tables:
                # Concatenate all tables (assuming same structure)
                return pd.concat(all_tables, ignore_index=True)
            return None
            
        except ImportError:
            logger.info("azure-ai-formrecognizer not installed")
            return None

    def _extract_tables_from_pdf_fallback(self, pdf_path: str) -> Optional[pd.DataFrame]:
        """Extract tables from PDF using tabula-py (fallback method)."""
        try:
            import tabula
            
            # Read all tables from PDF
            tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
            
            if tables:
                # Concatenate all tables
                return pd.concat(tables, ignore_index=True)
            return None
            
        except ImportError:
            logger.info("tabula-py not installed. Install with: pip install tabula-py")
            return None

    def _load_dataframe_to_table(self, table_name: str, df: pd.DataFrame) -> None:
        """Load a pandas DataFrame into a SQLite table."""
        # Clean column names (remove spaces, special chars)
        df.columns = [
            str(col).strip().replace(" ", "_").replace("-", "_").replace(".", "_")
            for col in df.columns
        ]

        # Write to SQLite
        df.to_sql(table_name, self._connection, if_exists="replace", index=False)

        logger.info(
            "Loaded %d rows into %s (%d columns)",
            len(df), table_name, len(df.columns)
        )

        # Cache schema
        self._cache_table_schema(table_name, df)

    def _cache_table_schema(self, table_name: str, df: pd.DataFrame) -> None:
        """Cache schema information for a table."""
        columns = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            sql_type = self._pandas_to_sql_type(dtype)
            columns.append(ColumnSchema(
                name=col,
                data_type=sql_type,
                nullable=df[col].isna().any(),
            ))

        self._schema_cache[table_name.upper()] = TableSchema(
            name=table_name,
            columns=columns,
        )

    def _pandas_to_sql_type(self, dtype: str) -> str:
        """Convert pandas dtype to SQL type string."""
        if "int" in dtype:
            return "INTEGER"
        elif "float" in dtype:
            return "DECIMAL"
        elif "datetime" in dtype:
            return "TIMESTAMP"
        elif "bool" in dtype:
            return "BOOLEAN"
        else:
            return "VARCHAR"

    def disconnect(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("SQLite connection closed")

    def execute_query(
        self,
        query: str,
        parameters: Dict[str, Any],
    ) -> QueryResult:
        """Execute a SQL query against SQLite."""
        if not self._connection:
            raise RuntimeError("Not connected to database")

        start_time = datetime.now()

        try:
            # Convert named parameters to positional for SQLite
            # SQLite uses ? or :name syntax
            processed_query = query
            param_values = []

            for key, value in parameters.items():
                # Replace :key with ?
                if f":{key}" in processed_query:
                    processed_query = processed_query.replace(f":{key}", "?")
                    param_values.append(value)

            logger.debug("Executing query: %s", processed_query[:200])

            # Execute query
            cursor = self._connection.cursor()
            if param_values:
                cursor.execute(processed_query, param_values)
            else:
                cursor.execute(processed_query)

            # Fetch results
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []

            # Convert to DataFrame
            df = pd.DataFrame(rows, columns=columns)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "Query executed: %d rows in %.1fms",
                len(df), execution_time
            )

            return QueryResult(
                data=df,
                row_count=len(df),
                execution_time_ms=execution_time,
                query=query,
            )

        except Exception as e:
            logger.error("Query execution failed: %s", e)
            raise

    def get_schema(
        self,
        table_name: Optional[str] = None,
        refresh: bool = False,
    ) -> Dict[str, TableSchema]:
        """Get schema information."""
        if table_name:
            upper_name = table_name.upper()
            if upper_name in self._schema_cache:
                return {table_name: self._schema_cache[upper_name]}
            return {}
        return dict(self._schema_cache)

    def test_connection(self) -> bool:
        """Test if connection is valid."""
        try:
            if self._connection:
                cursor = self._connection.cursor()
                cursor.execute("SELECT 1")
                return True
            return False
        except Exception:
            return False

    def get_table_names(self) -> List[str]:
        """Get list of available tables."""
        if not self._connection:
            return []

        cursor = self._connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]


def create_local_test_database(
    data_dir: Optional[str] = None,
) -> SQLiteDataSource:
    """
    Create a SQLite data source with test data for local development.

    Args:
        data_dir: Directory containing CSV files (defaults to project data/)

    Returns:
        Configured SQLiteDataSource ready for testing
    """
    if data_dir is None:
        # Default to project data directory
        data_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "data"

    data_path = Path(data_dir)

    # Find CSV files and map to table names
    csv_files = {}

    # Look for OrderHistoryLine CSV
    order_history_csv = data_path / "db_more_weu_prod_dbo_OrderHistoryLine.csv"
    if order_history_csv.exists():
        csv_files["OrderHistoryLine"] = str(order_history_csv)

    # Add other CSVs as they become available
    for csv_file in data_path.glob("*.csv"):
        # Extract table name from filename
        # e.g., "db_more_weu_prod_dbo_TableName.csv" -> "TableName"
        name = csv_file.stem
        if "_dbo_" in name:
            table_name = name.split("_dbo_")[-1]
        else:
            table_name = name

        if table_name not in csv_files:
            csv_files[table_name] = str(csv_file)

    logger.info("Found %d CSV files for local database", len(csv_files))

    return SQLiteDataSource(db_path=":memory:", csv_files=csv_files)
