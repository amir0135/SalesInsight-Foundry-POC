"""
Base Data Source Interface for SalesInsight POC.

This module defines the abstract base class for all data source connectors.
Implementations should handle connection management, query execution, and schema discovery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class ColumnSchema:
    """Schema information for a database column."""

    name: str
    data_type: str
    nullable: bool = True
    description: Optional[str] = None
    sample_values: Optional[List[str]] = None


@dataclass
class TableSchema:
    """Schema information for a database table."""

    name: str
    columns: List[ColumnSchema] = field(default_factory=list)
    row_count: Optional[int] = None
    description: Optional[str] = None


@dataclass
class SchemaCache:
    """Cached schema information with TTL."""

    tables: Dict[str, TableSchema] = field(default_factory=dict)
    last_refreshed: Optional[datetime] = None
    ttl_seconds: int = 300  # 5 minutes default

    def is_valid(self) -> bool:
        """Check if cache is still valid based on TTL."""
        if self.last_refreshed is None:
            return False
        elapsed = (datetime.now() - self.last_refreshed).total_seconds()
        return elapsed < self.ttl_seconds


@dataclass
class QueryResult:
    """Result of a query execution."""

    data: pd.DataFrame
    row_count: int
    execution_time_ms: float
    query: str
    parameters: Optional[Dict[str, Any]] = None


class BaseDataSource(ABC):
    """
    Abstract base class for data source connectors.

    All data source implementations (Snowflake, PostgreSQL, etc.) should
    inherit from this class and implement the abstract methods.

    Example:
        ```python
        class SnowflakeDataSource(BaseDataSource):
            def connect(self):
                # Implementation
                pass
        ```
    """

    def __init__(self):
        """Initialize the data source."""
        self._connected: bool = False
        self._schema_cache: SchemaCache = SchemaCache()

    @property
    def is_connected(self) -> bool:
        """Check if the data source is currently connected."""
        return self._connected

    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the data source.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close the connection to the data source.
        """
        pass

    @abstractmethod
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
    ) -> QueryResult:
        """
        Execute a SQL query and return results.

        Args:
            query: The SQL query to execute.
            parameters: Optional dictionary of query parameters for parameterized queries.
            timeout_seconds: Query timeout in seconds.

        Returns:
            QueryResult containing the data and metadata.

        Raises:
            QueryExecutionError: If query execution fails.
            TimeoutError: If query exceeds timeout.
        """
        pass

    @abstractmethod
    def get_schema(
        self, table_name: Optional[str] = None, refresh: bool = False
    ) -> Dict[str, TableSchema]:
        """
        Get schema information for tables.

        Args:
            table_name: Optional specific table name. If None, returns all tables.
            refresh: Force refresh of cached schema.

        Returns:
            Dictionary mapping table names to TableSchema objects.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the connection is alive and working.

        Returns:
            True if connection is valid, False otherwise.
        """
        pass

    def get_sample_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> List[str]:
        """
        Get sample values from a column for context.

        Args:
            table_name: Name of the table.
            column_name: Name of the column.
            limit: Maximum number of sample values.

        Returns:
            List of sample values as strings.
        """
        query = f"SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit}"
        result = self.execute_query(query)
        return result.data[column_name].astype(str).tolist()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
