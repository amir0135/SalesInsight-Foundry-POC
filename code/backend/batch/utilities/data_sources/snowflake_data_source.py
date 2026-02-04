"""
Snowflake Data Source Connector for SalesInsight POC.

This module implements the Snowflake connector for querying sales data.
It includes connection pooling, parameterized queries, and schema discovery.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import snowflake.connector
from snowflake.connector import DictCursor
from snowflake.connector.errors import DatabaseError, ProgrammingError

from .base_data_source import (
    BaseDataSource,
    ColumnSchema,
    QueryResult,
    TableSchema,
)

logger = logging.getLogger(__name__)


class SnowflakeConnectionError(Exception):
    """Exception raised when Snowflake connection fails."""

    pass


class SnowflakeQueryError(Exception):
    """Exception raised when Snowflake query execution fails."""

    pass


class SnowflakeDataSource(BaseDataSource):
    """
    Snowflake data source connector with connection pooling and security features.

    Example:
        ```python
        from backend.batch.utilities.data_sources import SnowflakeDataSource

        ds = SnowflakeDataSource(
            account="myaccount.us-east-1",
            user="service_user",
            password="secret",
            warehouse="COMPUTE_WH",
            database="SALES_DB",
            schema="PUBLIC"
        )

        with ds:
            result = ds.execute_query(
                "SELECT * FROM OrderHistoryLine WHERE Market = %(market)s",
                parameters={"market": "France"}
            )
            print(result.data.head())
        ```
    """

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: str = "PUBLIC",
        role: Optional[str] = None,
        connection_timeout: int = 30,
        login_timeout: int = 60,
    ):
        """
        Initialize Snowflake data source.

        Args:
            account: Snowflake account identifier (e.g., "myaccount.us-east-1").
            user: Snowflake username.
            password: Snowflake password (should come from Key Vault).
            warehouse: Snowflake warehouse name.
            database: Snowflake database name.
            schema: Snowflake schema name (default: "PUBLIC").
            role: Snowflake role for access control.
            connection_timeout: Connection timeout in seconds.
            login_timeout: Login timeout in seconds.
        """
        super().__init__()

        # Connection parameters
        self._account = account
        self._user = user
        self._password = password
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._role = role
        self._connection_timeout = connection_timeout
        self._login_timeout = login_timeout

        # Connection pool
        self._connection: Optional[snowflake.connector.SnowflakeConnection] = None

    def _load_from_env_helper(self) -> None:
        """Load configuration from EnvHelper if not provided."""
        # Import here to avoid circular imports
        from ..helpers.env_helper import EnvHelper

        env_helper = EnvHelper()

        if self._account is None:
            self._account = getattr(env_helper, "SNOWFLAKE_ACCOUNT", None)
        if self._user is None:
            self._user = getattr(env_helper, "SNOWFLAKE_USER", None)
        if self._password is None:
            self._password = getattr(env_helper, "SNOWFLAKE_PASSWORD", None)
        if self._warehouse is None:
            self._warehouse = getattr(env_helper, "SNOWFLAKE_WAREHOUSE", None)
        if self._database is None:
            self._database = getattr(env_helper, "SNOWFLAKE_DATABASE", None)
        if self._schema == "PUBLIC":
            self._schema = getattr(env_helper, "SNOWFLAKE_SCHEMA", "PUBLIC")
        if self._role is None:
            self._role = getattr(env_helper, "SNOWFLAKE_ROLE", None)

    def connect(self) -> None:
        """
        Establish connection to Snowflake.

        Raises:
            SnowflakeConnectionError: If connection fails.
        """
        if self._connected and self._connection is not None:
            return

        # Load from env helper if needed
        self._load_from_env_helper()

        # Validate required parameters
        if not all([self._account, self._user, self._password, self._database]):
            raise SnowflakeConnectionError(
                "Missing required Snowflake connection parameters. "
                "Ensure SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, "
                "and SNOWFLAKE_DATABASE are configured."
            )

        try:
            logger.info(
                f"Connecting to Snowflake account: {self._account}, "
                f"database: {self._database}"
            )

            self._connection = snowflake.connector.connect(
                account=self._account,
                user=self._user,
                password=self._password,
                warehouse=self._warehouse,
                database=self._database,
                schema=self._schema,
                role=self._role,
                network_timeout=self._connection_timeout,
                login_timeout=self._login_timeout,
                application="SalesInsightPOC",
            )

            self._connected = True
            logger.info("Successfully connected to Snowflake")

        except DatabaseError as e:
            logger.error(f"Failed to connect to Snowflake: {e}")
            raise SnowflakeConnectionError(f"Snowflake connection failed: {e}") from e

    def disconnect(self) -> None:
        """Close the Snowflake connection."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Disconnected from Snowflake")
            except Exception as e:
                logger.warning(f"Error closing Snowflake connection: {e}")
            finally:
                self._connection = None
                self._connected = False

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
    ) -> QueryResult:
        """
        Execute a SQL query with parameterized values.

        Args:
            query: The SQL query to execute (use %(param)s for parameters).
            parameters: Dictionary of query parameters.
            timeout_seconds: Query timeout in seconds.

        Returns:
            QueryResult with DataFrame and metadata.

        Raises:
            SnowflakeQueryError: If query execution fails.
        """
        if not self._connected or self._connection is None:
            self.connect()

        start_time = time.time()

        try:
            cursor = self._connection.cursor(DictCursor)

            # Log query for audit (without sensitive parameter values)
            logger.info(f"Executing query: {query[:200]}...")
            if parameters:
                logger.debug(f"Query parameters: {list(parameters.keys())}")

            # Execute with parameters (prevents SQL injection)
            cursor.execute(query, parameters or {})

            # Fetch results
            results = cursor.fetchall()
            df = pd.DataFrame(results) if results else pd.DataFrame()

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Query executed successfully. Rows: {len(df)}, "
                f"Time: {execution_time_ms:.2f}ms"
            )

            return QueryResult(
                data=df,
                row_count=len(df),
                execution_time_ms=execution_time_ms,
                query=query,
                parameters=parameters,
            )

        except ProgrammingError as e:
            logger.error(f"Query execution failed: {e}")
            raise SnowflakeQueryError(f"Query execution failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            raise SnowflakeQueryError(f"Unexpected query error: {e}") from e

    def get_schema(
        self, table_name: Optional[str] = None, refresh: bool = False
    ) -> Dict[str, TableSchema]:
        """
        Get schema information for Snowflake tables.

        Args:
            table_name: Specific table name (optional).
            refresh: Force cache refresh.

        Returns:
            Dictionary of table names to TableSchema objects.
        """
        # Check cache first
        if not refresh and self._schema_cache.is_valid():
            if table_name:
                return {table_name: self._schema_cache.tables.get(table_name)}
            return self._schema_cache.tables

        if not self._connected:
            self.connect()

        try:
            # Get table list
            if table_name:
                table_filter = f"AND TABLE_NAME = '{table_name}'"
            else:
                table_filter = ""

            tables_query = f"""
                SELECT TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{self._schema}' {table_filter}
            """
            tables_result = self.execute_query(tables_query)

            schemas: Dict[str, TableSchema] = {}

            for _, row in tables_result.data.iterrows():
                tbl_name = row["TABLE_NAME"]

                # Get columns for this table
                columns_query = f"""
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        COMMENT
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{self._schema}'
                      AND TABLE_NAME = '{tbl_name}'
                    ORDER BY ORDINAL_POSITION
                """
                columns_result = self.execute_query(columns_query)

                columns: List[ColumnSchema] = []
                for _, col_row in columns_result.data.iterrows():
                    columns.append(
                        ColumnSchema(
                            name=col_row["COLUMN_NAME"],
                            data_type=col_row["DATA_TYPE"],
                            nullable=col_row["IS_NULLABLE"] == "YES",
                            description=col_row.get("COMMENT"),
                        )
                    )

                # Get approximate row count
                count_query = f"SELECT COUNT(*) AS cnt FROM {tbl_name}"
                count_result = self.execute_query(count_query)
                row_count = (
                    int(count_result.data["CNT"].iloc[0])
                    if not count_result.data.empty
                    else None
                )

                schemas[tbl_name] = TableSchema(
                    name=tbl_name,
                    columns=columns,
                    row_count=row_count,
                )

            # Update cache
            self._schema_cache.tables = schemas
            self._schema_cache.last_refreshed = datetime.now()

            return schemas

        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test if Snowflake connection is alive.

        Returns:
            True if connection is valid.
        """
        try:
            if not self._connected:
                self.connect()
            result = self.execute_query("SELECT 1 AS test")
            return len(result.data) == 1
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def get_sample_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> List[str]:
        """
        Get sample distinct values from a column.

        Args:
            table_name: Name of the table.
            column_name: Name of the column.
            limit: Maximum number of values.

        Returns:
            List of sample values as strings.
        """
        query = f"""
            SELECT DISTINCT "{column_name}" AS val
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
            LIMIT {limit}
        """
        result = self.execute_query(query)
        return result.data["VAL"].astype(str).tolist()
