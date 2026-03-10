"""Factory for creating Database data sources."""

import logging
import os
from typing import Optional

from .data_source_interface import DatabaseDataSource
from .excel_data_source import ExcelDataSource
from .postgres_data_source import PostgresDataSource

logger = logging.getLogger(__name__)

_data_source_instance: Optional[DatabaseDataSource] = None


def is_database_enabled() -> bool:
    """Check if any database integration is configured.

    Returns True if Snowflake or PostgreSQL credentials are available.
    """
    if os.getenv("SALESINSIGHT_USE_LOCAL_DATA", "false").lower() == "true":
        return False
    if os.getenv("SNOWFLAKE_ACCOUNT"):
        return True
    if os.getenv("POSTGRES_HOST"):
        return True
    return False


def get_data_source() -> DatabaseDataSource:
    """
    Get the appropriate Database data source based on configuration.

    Returns:
        DatabaseDataSource instance (PostgreSQL or Excel fallback)

    Priority:
    1. PostgreSQL if POSTGRES_HOST is set
    2. Falls back to Excel/local CSV data

    This is a singleton - the same instance is returned on subsequent calls.
    """
    global _data_source_instance

    if _data_source_instance is not None:
        return _data_source_instance

    use_postgres = bool(os.getenv("POSTGRES_HOST"))

    if use_postgres:
        try:
            required_vars = [
                "POSTGRES_HOST",
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
            ]

            missing_vars = [var for var in required_vars if not os.getenv(var)]

            if missing_vars:
                logger.warning(
                    f"POSTGRES_HOST set but missing environment variables: {', '.join(missing_vars)}. "
                    "Falling back to Excel data source."
                )
                _data_source_instance = ExcelDataSource()
            else:
                logger.info("Initializing PostgreSQL data source")
                _data_source_instance = PostgresDataSource()
                logger.info("PostgreSQL data source active")

        except Exception as e:
            logger.error(
                f"Failed to initialize PostgreSQL data source: {str(e)}. "
                "Falling back to Excel data source."
            )
            _data_source_instance = ExcelDataSource()
    else:
        logger.info("Initializing Excel data source (no database configured)")
        _data_source_instance = ExcelDataSource()
        logger.info("Excel data source active")

    return _data_source_instance

    return _data_source_instance


def reset_data_source():
    """Reset the data source instance (useful for testing)."""
    global _data_source_instance
    _data_source_instance = None
