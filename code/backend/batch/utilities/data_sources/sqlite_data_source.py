"""
Local SQLite Data Source for testing SalesInsight without Snowflake.

This module provides a SQLite-based data source that can load CSV files
for local development and testing.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .base_data_source import BaseDataSource, ColumnSchema, QueryResult, TableSchema

logger = logging.getLogger(__name__)


class SQLiteDataSource(BaseDataSource):
    """
    SQLite-based data source for local testing.

    This data source loads CSV files into an in-memory SQLite database,
    allowing local testing of NL2SQL queries without Snowflake.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        csv_files: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize SQLite data source.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory
            csv_files: Dict mapping table names to CSV file paths
        """
        self._db_path = db_path
        self._csv_files = csv_files or {}
        self._connection: Optional[sqlite3.Connection] = None
        self._schema_cache: Dict[str, TableSchema] = {}

    def connect(self) -> None:
        """Connect to SQLite database and load CSV files."""
        if self._connection is not None:
            return

        logger.info("Connecting to SQLite database: %s", self._db_path)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row

        # Load CSV files into tables
        for table_name, csv_path in self._csv_files.items():
            self._load_csv_to_table(table_name, csv_path)

        logger.info("SQLite connection established with %d tables", len(self._csv_files))

    def _load_csv_to_table(self, table_name: str, csv_path: str) -> None:
        """Load a CSV file into a SQLite table."""
        path = Path(csv_path)
        if not path.exists():
            logger.warning("CSV file not found: %s", csv_path)
            return

        logger.info("Loading %s from %s", table_name, csv_path)

        try:
            # Read CSV with pandas
            df = pd.read_csv(csv_path, low_memory=False)

            # Clean column names (remove spaces, special chars)
            df.columns = [
                col.strip().replace(" ", "_").replace("-", "_")
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

        except Exception as e:
            logger.error("Failed to load CSV %s: %s", csv_path, e)
            raise

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
