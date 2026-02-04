"""
Schema Discovery Module for SalesInsight POC.

This module provides functionality for discovering and caching database schemas
from various data sources. It supports introspection of tables, columns, and
their metadata to provide context for NL2SQL generation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from .base_data_source import BaseDataSource

logger = logging.getLogger(__name__)


@dataclass
class SchemaDiscoveryConfig:
    """Configuration for schema discovery behavior."""

    cache_ttl_minutes: int = 60
    include_views: bool = False
    include_system_tables: bool = False
    max_tables: int = 100
    sample_rows_for_stats: int = 1000


@dataclass
class ColumnStatistics:
    """Statistics about a column for query optimization hints."""

    distinct_count: Optional[int] = None
    null_count: Optional[int] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    sample_values: list = field(default_factory=list)


@dataclass
class EnrichedColumnSchema:
    """Extended column schema with statistics and metadata."""

    name: str
    data_type: str
    nullable: bool = True
    description: Optional[str] = None
    statistics: Optional[ColumnStatistics] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_reference: Optional[str] = None


@dataclass
class EnrichedTableSchema:
    """Extended table schema with enriched column information."""

    name: str
    columns: list[EnrichedColumnSchema]
    description: Optional[str] = None
    row_count: Optional[int] = None
    last_updated: Optional[datetime] = None


class SchemaCache:
    """In-memory cache for discovered schemas with TTL support."""

    def __init__(self, ttl_minutes: int = 60):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp."""
        self._cache[key] = (value, datetime.now())

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate specific key or entire cache."""
        if key is None:
            self._cache.clear()
        elif key in self._cache:
            del self._cache[key]

    def get_cache_stats(self) -> dict:
        """Return cache statistics."""
        now = datetime.now()
        valid_entries = sum(
            1 for _, (_, ts) in self._cache.items() if now - ts < self._ttl
        )
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._cache) - valid_entries,
        }


class SchemaDiscovery:
    """
    Discovers and caches database schema information from data sources.

    This class provides methods to introspect database schemas, retrieve
    table and column metadata, and cache results for efficient NL2SQL
    context generation.
    """

    def __init__(
        self,
        data_source: BaseDataSource,
        config: Optional[SchemaDiscoveryConfig] = None,
    ):
        """
        Initialize schema discovery with a data source.

        Args:
            data_source: The data source to introspect
            config: Optional configuration for discovery behavior
        """
        self.data_source = data_source
        self.config = config or SchemaDiscoveryConfig()
        self._cache = SchemaCache(ttl_minutes=self.config.cache_ttl_minutes)
        logger.info(
            f"SchemaDiscovery initialized for {type(data_source).__name__}"
        )

    def discover_tables(self, schema_name: Optional[str] = None) -> list[str]:
        """
        Discover all available tables in the data source.

        Args:
            schema_name: Optional schema/database name to filter tables

        Returns:
            List of table names
        """
        cache_key = f"tables:{schema_name or 'default'}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Returning cached table list for {cache_key}")
            return cached

        try:
            # Use the data source's schema discovery
            schema_info = self.data_source.get_schema(
                table_name=None,  # Get all tables
            )

            tables = list(schema_info.keys())

            # Filter based on configuration
            if not self.config.include_system_tables:
                tables = [
                    t for t in tables
                    if not t.startswith("_") and not t.startswith("sys")
                ]

            # Apply max tables limit
            tables = tables[: self.config.max_tables]

            self._cache.set(cache_key, tables)
            logger.info(f"Discovered {len(tables)} tables")
            return tables

        except Exception as e:
            logger.error(f"Error discovering tables: {e}")
            raise SchemaDiscoveryError(f"Failed to discover tables: {e}") from e

    def get_table_schema(
        self,
        table_name: str,
        include_statistics: bool = False,
    ) -> EnrichedTableSchema:
        """
        Get detailed schema information for a specific table.

        Args:
            table_name: Name of the table to introspect
            include_statistics: Whether to include column statistics

        Returns:
            EnrichedTableSchema with column details
        """
        cache_key = f"schema:{table_name}:{include_statistics}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Returning cached schema for {table_name}")
            return cached

        try:
            # Get base schema from data source
            schema_dict = self.data_source.get_schema(table_name=table_name)

            if not schema_dict or table_name not in schema_dict:
                raise SchemaDiscoveryError(f"Table '{table_name}' not found")

            base_schema = schema_dict[table_name]

            # Convert to enriched schema
            enriched_columns = []
            for col in base_schema.columns:
                enriched_col = EnrichedColumnSchema(
                    name=col.name,
                    data_type=col.data_type,
                    nullable=col.nullable,
                    description=col.description,
                )

                if include_statistics:
                    enriched_col.statistics = self._get_column_statistics(
                        table_name, col.name
                    )

                enriched_columns.append(enriched_col)

            # Get row count
            row_count = self._get_table_row_count(table_name)

            enriched_schema = EnrichedTableSchema(
                name=table_name,
                columns=enriched_columns,
                row_count=row_count,
                last_updated=datetime.now(),
            )

            self._cache.set(cache_key, enriched_schema)
            logger.info(
                f"Retrieved schema for {table_name}: {len(enriched_columns)} columns"
            )
            return enriched_schema

        except SchemaDiscoveryError:
            raise
        except Exception as e:
            logger.error(f"Error getting schema for {table_name}: {e}")
            raise SchemaDiscoveryError(
                f"Failed to get schema for {table_name}: {e}"
            ) from e

    def get_schema_context_for_nl2sql(
        self,
        table_names: Optional[list[str]] = None,
        include_sample_values: bool = True,
    ) -> str:
        """
        Generate schema context string for NL2SQL prompt injection.

        This method creates a formatted string describing the database schema
        that can be included in prompts to the LLM for SQL generation.

        Args:
            table_names: Optional list of tables to include (all if None)
            include_sample_values: Whether to include sample values for context

        Returns:
            Formatted schema description string
        """
        if table_names is None:
            table_names = self.discover_tables()

        context_parts = ["## Available Database Schema\n"]

        for table_name in table_names:
            try:
                schema = self.get_table_schema(
                    table_name, include_statistics=include_sample_values
                )
                context_parts.append(self._format_table_for_prompt(schema))
            except SchemaDiscoveryError as e:
                logger.warning(f"Skipping table {table_name}: {e}")
                continue

        return "\n".join(context_parts)

    def _format_table_for_prompt(self, schema: EnrichedTableSchema) -> str:
        """Format a table schema for inclusion in an NL2SQL prompt."""
        lines = [f"\n### Table: {schema.name}"]

        if schema.row_count is not None:
            lines.append(f"Row count: ~{schema.row_count:,}")

        if schema.description:
            lines.append(f"Description: {schema.description}")

        lines.append("\nColumns:")
        for col in schema.columns:
            col_desc = f"  - {col.name} ({col.data_type})"
            if not col.nullable:
                col_desc += " NOT NULL"
            if col.is_primary_key:
                col_desc += " PRIMARY KEY"
            if col.description:
                col_desc += f" -- {col.description}"
            lines.append(col_desc)

            # Add sample values if available
            if col.statistics and col.statistics.sample_values:
                samples = ", ".join(
                    repr(v) for v in col.statistics.sample_values[:5]
                )
                lines.append(f"    Sample values: {samples}")

        return "\n".join(lines)

    def _get_table_row_count(self, table_name: str) -> Optional[int]:
        """Get approximate row count for a table."""
        try:
            result = self.data_source.execute_query(
                f"SELECT COUNT(*) as cnt FROM {table_name}",  # noqa: S608
                parameters={},
            )
            if not result.data.empty:
                # Handle DataFrame result
                row = result.data.iloc[0]
                return int(row.get("cnt", row.get("CNT", 0)))
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not get row count for %s: %s", table_name, e)
            return None

    def _get_column_statistics(
        self,
        table_name: str,
        column_name: str,
    ) -> ColumnStatistics:
        """Get statistics for a specific column."""
        stats = ColumnStatistics()

        try:
            # Get sample values
            sample_query = f"""
                SELECT DISTINCT {column_name}
                FROM {table_name}
                WHERE {column_name} IS NOT NULL
                LIMIT 10
            """  # noqa: S608

            result = self.data_source.execute_query(sample_query, parameters={})
            if not result.data.empty:
                # Handle DataFrame - extract column values
                col_key = column_name if column_name in result.data.columns else column_name.upper()
                if col_key in result.data.columns:
                    stats.sample_values = result.data[col_key].tolist()

        except Exception as e:  # noqa: BLE001
            logger.debug("Could not get statistics for %s: %s", column_name, e)

        return stats

    def refresh_cache(self, table_name: Optional[str] = None) -> None:
        """
        Refresh cached schema information.

        Args:
            table_name: Specific table to refresh, or None for all
        """
        if table_name:
            self._cache.invalidate(f"schema:{table_name}:True")
            self._cache.invalidate(f"schema:{table_name}:False")
            logger.info(f"Refreshed cache for table: {table_name}")
        else:
            self._cache.invalidate()
            logger.info("Refreshed entire schema cache")

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        return self._cache.get_cache_stats()


class SchemaDiscoveryError(Exception):
    """Exception raised when schema discovery fails."""

    pass
