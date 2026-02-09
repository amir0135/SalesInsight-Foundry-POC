"""
SalesInsight Agent for natural language sales analytics.

This module provides the core agent that orchestrates:
1. Natural language understanding
2. SQL generation and validation
3. Query execution
4. Visualization generation
5. Response formatting
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union
from uuid import uuid4

import pandas as pd
from openai import AzureOpenAI

from ..data_sources import SchemaDiscovery, SnowflakeDataSource
from ..data_sources.sqlite_data_source import SQLiteDataSource
from ..helpers.env_helper import EnvHelper
from ..nl2sql import NL2SQLGenerator, PromptBuilder, QueryValidator
from ..visualization import ChartGenerator, ChartConfig, ChartType

logger = logging.getLogger(__name__)


@dataclass
class SalesInsightConfig:
    """Configuration for the SalesInsight agent."""

    # Data source settings
    snowflake_account: str = ""
    snowflake_warehouse: str = ""
    snowflake_database: str = ""
    snowflake_schema: str = "PUBLIC"

    # Model settings
    model_name: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 2048

    # Query settings
    max_rows: int = 1000
    query_timeout: float = 30.0

    # Visualization settings
    auto_generate_chart: bool = True
    default_chart_type: str = "horizontal_bar"
    max_chart_items: int = 10

    # Security settings
    validate_queries: bool = True
    log_queries: bool = True


@dataclass
class SalesInsightResponse:
    """Response from the SalesInsight agent."""

    request_id: str
    question: str
    sql_query: str
    data: Optional[pd.DataFrame] = None
    chart_base64: Optional[str] = None
    explanation: str = ""
    summary: str = ""
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    row_count: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "request_id": self.request_id,
            "question": self.question,
            "sql_query": self.sql_query,
            "explanation": self.explanation,
            "summary": self.summary,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }

        if self.data is not None:
            result["data"] = self.data.to_dict(orient="records")

        if self.chart_base64:
            result["chart"] = {
                "image_base64": self.chart_base64,
                "format": "png",
            }

        if self.error:
            result["error"] = self.error

        return result


class SalesInsightAgent:
    """
    AI Agent for natural language sales data analytics.

    This agent orchestrates the full pipeline of:
    1. Receiving natural language questions about sales data
    2. Generating validated SQL queries using GPT-4o
    3. Executing queries against Snowflake
    4. Creating visualizations from results
    5. Generating natural language summaries

    Example:
        ```python
        agent = SalesInsightAgent()
        response = await agent.query(
            "What are the top 10 products by revenue this year?"
        )
        print(response.summary)
        print(response.chart_base64)  # Base64 PNG image
        ```
    """

    def __init__(
        self,
        config: Optional[SalesInsightConfig] = None,
        data_source: Optional[Union[SnowflakeDataSource, SQLiteDataSource]] = None,
        openai_client: Optional[AzureOpenAI] = None,
    ):
        """
        Initialize the SalesInsight agent.

        Args:
            config: Optional configuration (uses env vars if not provided)
            data_source: Optional pre-configured data source
            openai_client: Optional pre-configured OpenAI client
        """
        self.config = config or self._load_config_from_env()
        self.env_helper = EnvHelper()

        # Initialize OpenAI client
        if openai_client:
            self._openai_client = openai_client
        else:
            self._openai_client = self._create_openai_client()

        # Initialize data source
        if data_source:
            self._data_source = data_source
        else:
            self._data_source = self._create_data_source()

        # Connect data source and load data BEFORE schema discovery
        # This ensures tables exist when we discover the schema
        self._data_source.connect()

        # Initialize components
        self._schema_discovery = SchemaDiscovery(self._data_source)
        self._sql_generator = NL2SQLGenerator(openai_client=self._openai_client)
        
        # Build query validator dynamically from discovered schema
        # This auto-allows all actual tables/columns - no manual config needed!
        self._query_validator = self._create_query_validator()
        
        self._prompt_builder = PromptBuilder()
        self._chart_generator = ChartGenerator()

        logger.info("SalesInsightAgent initialized")

    def _load_config_from_env(self) -> SalesInsightConfig:
        """Load configuration from environment variables."""
        env = EnvHelper()
        return SalesInsightConfig(
            snowflake_account=env.SNOWFLAKE_ACCOUNT,
            snowflake_warehouse=env.SNOWFLAKE_WAREHOUSE,
            snowflake_database=env.SNOWFLAKE_DATABASE,
            snowflake_schema=env.SNOWFLAKE_SCHEMA,
            model_name=env.AZURE_OPENAI_MODEL,
        )

    def _create_openai_client(self) -> AzureOpenAI:
        """Create Azure OpenAI client with key or RBAC authentication."""
        if self.env_helper.is_auth_type_keys():
            return AzureOpenAI(
                api_key=self.env_helper.AZURE_OPENAI_API_KEY,
                api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
            )
        else:
            return AzureOpenAI(
                azure_ad_token_provider=self.env_helper.AZURE_TOKEN_PROVIDER,
                api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
                azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
            )

    def _create_query_validator(self) -> QueryValidator:
        """Create query validator with allowlist built from actual schema.
        
        This dynamically discovers tables and columns from the data source,
        so you don't need to manually maintain an allowlist YAML file.
        """
        # Get all tables (returns list of table names as strings)
        table_names = self._schema_discovery.discover_tables()
        
        # Build schema dict: {table_name: [column_names]}
        schema = {}
        for table_name in table_names:
            table_schema = self._schema_discovery.get_table_schema(table_name)
            schema[table_name] = [col.name for col in table_schema.columns]
        
        logger.info(f"Built dynamic allowlist from schema: {list(schema.keys())}")
        
        # Create validator from schema - no YAML config needed!
        return QueryValidator.from_schema(schema)

    def _create_data_source(self) -> Union[SnowflakeDataSource, SQLiteDataSource]:
        """Create data source based on environment configuration.
        
        Uses SQLite with local files if SALESINSIGHT_USE_LOCAL_DATA=true,
        otherwise connects to Snowflake.
        
        Local mode supports:
        - CSV files (.csv)
        - Excel files (.xlsx, .xls)
        - PDF tables (.pdf) - extracted via Azure Document Intelligence
        """
        use_local = os.environ.get("SALESINSIGHT_USE_LOCAL_DATA", "false").lower() == "true"
        
        if use_local:
            return self._create_local_data_source()
        else:
            return SnowflakeDataSource(
                account=self.config.snowflake_account,
                warehouse=self.config.snowflake_warehouse,
                database=self.config.snowflake_database,
                schema=self.config.snowflake_schema,
            )

    def _create_local_data_source(self) -> SQLiteDataSource:
        """Create local SQLite data source from files.
        
        In production (Azure): Downloads CSV from Azure Blob Storage
        In local dev: Loads from data/ folder
        
        Automatically discovers and loads all supported files:
        - CSV files become tables named after the file
        - Excel files become tables named after the file
        """
        from pathlib import Path
        import tempfile
        
        is_production = os.environ.get("WEBSITE_SITE_NAME") is not None
        
        data_files = {}
        
        # In production, try to load from blob storage first
        if is_production:
            try:
                from ..helpers.azure_blob_storage_client import AzureBlobStorageClient
                import json
                
                # Check for uploaded CSV config
                config_client = AzureBlobStorageClient(container_name="config")
                try:
                    config_data = config_client.download_file("database_connection.json")
                    config = json.loads(config_data)
                    blob_path = config.get("local", {}).get("blob_path")
                    
                    if blob_path:
                        logger.info("Loading CSV from blob storage: %s", blob_path)
                        blob_client = AzureBlobStorageClient(container_name="salesdata")
                        csv_data = blob_client.download_file(blob_path)
                        
                        # Save to temp file
                        temp_dir = tempfile.mkdtemp()
                        filename = os.path.basename(blob_path)
                        temp_path = os.path.join(temp_dir, filename)
                        with open(temp_path, "wb") as f:
                            f.write(csv_data)
                        
                        table_name = self._file_to_table_name(Path(filename).stem)
                        data_files[table_name] = temp_path
                        logger.info("Loaded blob CSV as table: %s", table_name)
                except Exception as e:
                    logger.warning("Could not load config from blob: %s", e)
                    
            except Exception as e:
                logger.warning("Blob storage not available: %s", e)
        
        # Fall back to local data directory
        if not data_files:
            data_dir = os.environ.get(
                "SALESINSIGHT_DATA_DIR",
                os.path.join(os.path.dirname(__file__), "../../../../../data")
            )
            data_dir = os.path.abspath(data_dir)
            
            logger.info("Scanning data directory for files: %s", data_dir)
            
            supported_extensions = {'.csv', '.xlsx', '.xls'}
            
            if os.path.isdir(data_dir):
                for file_path in Path(data_dir).iterdir():
                    if file_path.suffix.lower() in supported_extensions:
                        table_name = self._file_to_table_name(file_path.stem)
                        data_files[table_name] = str(file_path)
                        logger.info("Found data file: %s -> table '%s'", file_path.name, table_name)
        
        # Allow explicit file override
        explicit_path = os.environ.get("SALESINSIGHT_CSV_PATH")
        if explicit_path and os.path.exists(explicit_path):
            table_name = self._file_to_table_name(Path(explicit_path).stem)
            data_files[table_name] = explicit_path
        
        if not data_files:
            logger.warning("No data files found")
        
        logger.info("Using local SQLite data source with %d files", len(data_files))
        return SQLiteDataSource.from_files(data_files)

    def _file_to_table_name(self, filename: str) -> str:
        """Convert a filename to a valid SQL table name."""
        import re
        # Remove common prefixes and clean up
        name = filename.lower()
        # Remove common database prefixes
        name = re.sub(r'^db_[a-z]+_[a-z]+_[a-z]+_dbo_', '', name)
        # Replace special chars with underscore
        name = re.sub(r'[^a-z0-9]', '_', name)
        # Remove multiple underscores
        name = re.sub(r'_+', '_', name)
        # Remove leading/trailing underscores
        name = name.strip('_')
        return name or "data"

    async def query(
        self,
        question: str,
        generate_chart: bool = True,
        chat_history: Optional[list[dict]] = None,
    ) -> SalesInsightResponse:
        """
        Process a natural language question about sales data.

        This is the main entry point for the agent. It:
        1. Generates SQL from the natural language question
        2. Validates the SQL for security
        3. Executes the query against Snowflake
        4. Optionally generates a visualization
        5. Creates a natural language summary

        Args:
            question: Natural language question about sales data
            generate_chart: Whether to generate a chart from results
            chat_history: Optional conversation history for context

        Returns:
            SalesInsightResponse with data, chart, and summary
        """
        request_id = str(uuid4())
        start_time = datetime.now()

        logger.info("Processing query request_id=%s: %s", request_id, question[:100])

        try:
            # Step 1: Get schema context
            schema_context = self._schema_discovery.get_schema_context_for_nl2sql()

            # Step 2: Build prompts
            system_prompt = self._prompt_builder.build_system_prompt(schema_context)

            # Step 3: Generate SQL
            generated = self._sql_generator.generate(
                question=question,
                schema_context=schema_context,
                system_prompt=system_prompt,
            )

            sql_query = generated.sql
            explanation = generated.explanation or ""

            # Step 4: Validate SQL
            if self.config.validate_queries:
                validation = self._query_validator.validate(sql_query)
                if not validation.is_valid:
                    raise SalesInsightError(
                        f"Query validation failed: {'; '.join(validation.errors)}"
                    )
                sql_query = validation.sanitized_sql or sql_query

            # Step 5: Execute query
            self._data_source.connect()
            try:
                result = self._data_source.execute_query(sql_query, parameters={})
                data = result.data
                row_count = len(data)
            finally:
                self._data_source.disconnect()

            # Step 6: Generate chart if requested and data is suitable
            chart_base64 = None
            if generate_chart and self.config.auto_generate_chart:
                chart_base64 = self._generate_chart_for_data(data, question)

            # Step 7: Generate summary
            summary = self._generate_summary(question, data, explanation)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "Query completed request_id=%s, rows=%d, time=%.0fms",
                request_id, row_count, execution_time
            )

            return SalesInsightResponse(
                request_id=request_id,
                question=question,
                sql_query=sql_query,
                data=data,
                chart_base64=chart_base64,
                explanation=explanation,
                summary=summary,
                row_count=row_count,
                execution_time_ms=execution_time,
                metadata={
                    "model": generated.model_used,
                    "tokens_used": generated.tokens_used,
                    "confidence": generated.confidence_score,
                },
            )

        except SalesInsightError:
            raise
        except Exception as e:
            logger.error("Query failed request_id=%s: %s", request_id, e)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return SalesInsightResponse(
                request_id=request_id,
                question=question,
                sql_query="",
                error=str(e),
                execution_time_ms=execution_time,
            )

    def _generate_chart_for_data(
        self,
        data: pd.DataFrame,
        question: str,
    ) -> Optional[str]:
        """Generate an appropriate chart for the query results."""
        if data.empty or len(data.columns) < 2:
            return None

        try:
            # Infer chart type from data structure
            chart_config = self._infer_chart_config(data, question)

            if chart_config:
                chart = self._chart_generator.generate(data, chart_config)
                return chart.image_base64

        except Exception as e:
            logger.warning("Chart generation failed: %s", e)

        return None

    def _infer_chart_config(
        self,
        data: pd.DataFrame,
        question: str,
    ) -> Optional[ChartConfig]:
        """Infer appropriate chart configuration from data and question."""
        # Identify column types
        numeric_cols = data.select_dtypes(include=["number"]).columns.tolist()
        text_cols = data.select_dtypes(include=["object"]).columns.tolist()

        if not numeric_cols or not text_cols:
            return None

        # Check for ranking keywords
        ranking_keywords = ["top", "bottom", "best", "worst", "highest", "lowest"]
        is_ranking = any(kw in question.lower() for kw in ranking_keywords)

        # Default: use first text column for x, first numeric for y
        x_col = text_cols[0]
        y_col = numeric_cols[0]

        if is_ranking:
            return ChartConfig(
                chart_type=ChartType.HORIZONTAL_BAR,
                title=self._generate_chart_title(question),
                x_column=x_col,
                y_column=y_col,
                color_palette="Blues_r",
                max_items=self.config.max_chart_items,
                sort_values=True,
                sort_ascending=False,
            )
        else:
            return ChartConfig(
                chart_type=ChartType.BAR,
                title=self._generate_chart_title(question),
                x_column=x_col,
                y_column=y_col,
                color_palette="viridis",
                max_items=self.config.max_chart_items,
            )

    def _generate_chart_title(self, question: str) -> str:
        """Generate a chart title from the question."""
        # Simple title generation - could be enhanced with LLM
        title = question.strip().rstrip("?").rstrip(".")
        if len(title) > 60:
            title = title[:57] + "..."
        return title.title()

    def _generate_summary(
        self,
        question: str,
        data: pd.DataFrame,
        explanation: str,
    ) -> str:
        """Generate a natural language summary of the results."""
        if data.empty:
            return "No data found matching your query."

        # Get basic stats
        row_count = len(data)
        col_count = len(data.columns)

        # Find numeric columns for aggregation
        numeric_cols = data.select_dtypes(include=["number"]).columns.tolist()

        summary_parts = [f"Found {row_count} results."]

        if numeric_cols:
            first_numeric = numeric_cols[0]
            total = data[first_numeric].sum()
            summary_parts.append(
                f"Total {first_numeric}: {total:,.0f}"
            )

            if row_count > 1:
                top_value = data[first_numeric].max()
                summary_parts.append(f"Maximum value: {top_value:,.0f}")

        if explanation:
            summary_parts.append(explanation)

        return " ".join(summary_parts)

    def test_connection(self) -> bool:
        """Test connectivity to all required services."""
        try:
            # Test Snowflake
            self._data_source.connect()
            snowflake_ok = self._data_source.test_connection()
            self._data_source.disconnect()

            if not snowflake_ok:
                logger.error("Snowflake connection test failed")
                return False

            # Test OpenAI (simple completion)
            response = self._openai_client.chat.completions.create(
                model=self.env_helper.AZURE_OPENAI_MODEL,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            if not response.choices:
                logger.error("OpenAI connection test failed")
                return False

            logger.info("All connection tests passed")
            return True

        except Exception as e:
            logger.error("Connection test failed: %s", e)
            return False


class SalesInsightError(Exception):
    """Exception raised when SalesInsight agent encounters an error."""

    pass
