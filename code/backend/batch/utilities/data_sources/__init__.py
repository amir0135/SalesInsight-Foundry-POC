"""
Data Sources module for SalesInsight POC.

This module provides data source connectors for querying sales data.
"""

from .base_data_source import (
    BaseDataSource,
    ColumnSchema,
    QueryResult,
    SchemaCache,
    TableSchema,
)
from .schema_discovery import (
    ColumnStatistics,
    EnrichedColumnSchema,
    EnrichedTableSchema,
    SchemaDiscovery,
    SchemaDiscoveryConfig,
    SchemaDiscoveryError,
)
from .snowflake_data_source import (
    SnowflakeConnectionError,
    SnowflakeDataSource,
    SnowflakeQueryError,
)

__all__ = [
    # Base data source
    "BaseDataSource",
    "ColumnSchema",
    "TableSchema",
    "SchemaCache",
    "QueryResult",
    # Snowflake connector
    "SnowflakeDataSource",
    "SnowflakeConnectionError",
    "SnowflakeQueryError",
    # Schema discovery
    "SchemaDiscovery",
    "SchemaDiscoveryConfig",
    "SchemaDiscoveryError",
    "EnrichedTableSchema",
    "EnrichedColumnSchema",
    "ColumnStatistics",
]
