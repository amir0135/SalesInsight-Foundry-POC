"""
Agent Tools for SalesInsight AI Agent.

This module provides tool definitions that can be used with
Azure AI Foundry or OpenAI function calling to enable the
agent to interact with sales data.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from ..data_sources import SnowflakeDataSource, SchemaDiscovery
from ..nl2sql import NL2SQLGenerator, QueryValidator, PromptBuilder
from ..visualization import ChartGenerator, ChartConfig, ChartType

logger = logging.getLogger(__name__)


# Tool schema definitions for Azure AI Foundry / OpenAI function calling
QUERY_SALES_DATA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_sales_data",
        "description": (
            "Execute a natural language query against the sales database to retrieve "
            "sales data, revenue figures, customer information, and product analytics. "
            "Use this tool when the user asks questions about sales performance, "
            "rankings, trends, or any data analysis related to sales."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "The natural language question about sales data. "
                        "Examples: 'What are the top 10 products by revenue?', "
                        "'Show me sales by region for Q1', "
                        "'Compare customer purchases between 2023 and 2024'"
                    ),
                },
                "include_chart": {
                    "type": "boolean",
                    "description": "Whether to generate a visualization chart with the results",
                    "default": True,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 100,
                },
            },
            "required": ["question"],
        },
    },
}

GENERATE_CHART_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_chart",
        "description": (
            "Generate a visualization chart from previously queried sales data. "
            "Use this tool when the user wants to visualize data that has already "
            "been retrieved, or to create a different type of chart."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "horizontal_bar", "line", "pie"],
                    "description": "Type of chart to generate",
                    "default": "horizontal_bar",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the chart",
                },
                "x_column": {
                    "type": "string",
                    "description": "Column name to use for x-axis (categories)",
                },
                "y_column": {
                    "type": "string",
                    "description": "Column name to use for y-axis (values)",
                },
            },
            "required": ["chart_type"],
        },
    },
}

GET_SCHEMA_INFO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_schema_info",
        "description": (
            "Get information about the available sales database schema, "
            "including table names, column names, and data types. "
            "Use this when you need to understand what data is available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Optional specific table to get schema for",
                },
            },
            "required": [],
        },
    },
}


@dataclass
class ToolResult:
    """Result from executing a tool."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "success": self.success,
            "metadata": self.metadata,
        }
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        return result

    def to_json(self) -> str:
        """Convert to JSON string for function response."""
        return json.dumps(self.to_dict(), default=str)


class BaseTool(ABC):
    """Abstract base class for agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        ...

    @property
    @abstractmethod
    def schema(self) -> dict:
        """Tool schema for function calling."""
        ...

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        ...


class QuerySalesDataTool(BaseTool):
    """
    Tool for querying sales data using natural language.

    This tool converts natural language questions to SQL,
    executes them against Snowflake, and returns the results.
    """

    def __init__(
        self,
        data_source: SnowflakeDataSource,
        sql_generator: NL2SQLGenerator,
        query_validator: QueryValidator,
        prompt_builder: PromptBuilder,
        schema_discovery: SchemaDiscovery,
        chart_generator: Optional[ChartGenerator] = None,
    ):
        """Initialize the tool with required components."""
        self.data_source = data_source
        self.sql_generator = sql_generator
        self.query_validator = query_validator
        self.prompt_builder = prompt_builder
        self.schema_discovery = schema_discovery
        self.chart_generator = chart_generator or ChartGenerator()

    @property
    def name(self) -> str:
        return "query_sales_data"

    @property
    def schema(self) -> dict:
        return QUERY_SALES_DATA_SCHEMA

    def execute(
        self,
        question: str,
        include_chart: bool = True,
        max_results: int = 100,
        **kwargs,
    ) -> ToolResult:
        """
        Execute a natural language query against sales data.

        Args:
            question: Natural language question
            include_chart: Whether to generate a chart
            max_results: Maximum results to return

        Returns:
            ToolResult with query results
        """
        try:
            logger.info("QuerySalesDataTool executing: %s", question[:100])

            # Get schema context
            schema_context = self.schema_discovery.get_schema_context_for_nl2sql()

            # Build prompts
            system_prompt = self.prompt_builder.build_system_prompt(schema_context)

            # Generate SQL
            generated = self.sql_generator.generate(
                question=question,
                schema_context=schema_context,
                system_prompt=system_prompt,
            )

            # Validate SQL
            validation = self.query_validator.validate(generated.sql)
            if not validation.is_valid:
                return ToolResult(
                    success=False,
                    error=f"Query validation failed: {'; '.join(validation.errors)}",
                )

            sql_query = validation.sanitized_sql or generated.sql

            # Execute query
            self.data_source.connect()
            try:
                result = self.data_source.execute_query(sql_query, parameters={})
                data = result.data

                # Limit results
                if len(data) > max_results:
                    data = data.head(max_results)

            finally:
                self.data_source.disconnect()

            # Prepare response
            response_data = {
                "sql": sql_query,
                "explanation": generated.explanation,
                "row_count": len(data),
                "columns": list(data.columns),
                "data": data.to_dict(orient="records"),
            }

            # Generate chart if requested
            if include_chart and not data.empty and len(data.columns) >= 2:
                try:
                    chart_config = self._infer_chart_config(data, question)
                    if chart_config:
                        chart = self.chart_generator.generate(data, chart_config)
                        response_data["chart_base64"] = chart.image_base64
                except Exception as e:
                    logger.warning("Chart generation failed: %s", e)

            return ToolResult(
                success=True,
                data=response_data,
                metadata={
                    "tokens_used": generated.tokens_used,
                    "confidence": generated.confidence_score,
                },
            )

        except Exception as e:
            logger.error("QuerySalesDataTool failed: %s", e)
            return ToolResult(success=False, error=str(e))

    def _infer_chart_config(
        self,
        data: pd.DataFrame,
        question: str,
    ) -> Optional[ChartConfig]:
        """Infer chart configuration from data and question."""
        numeric_cols = data.select_dtypes(include=["number"]).columns.tolist()
        text_cols = data.select_dtypes(include=["object"]).columns.tolist()

        if not numeric_cols or not text_cols:
            return None

        x_col = text_cols[0]
        y_col = numeric_cols[0]

        ranking_keywords = ["top", "bottom", "best", "worst", "highest", "lowest"]
        is_ranking = any(kw in question.lower() for kw in ranking_keywords)

        chart_type = ChartType.HORIZONTAL_BAR if is_ranking else ChartType.BAR

        return ChartConfig(
            chart_type=chart_type,
            title=question[:50] + ("..." if len(question) > 50 else ""),
            x_column=x_col,
            y_column=y_col,
            max_items=10,
            sort_values=True,
        )


class GenerateChartTool(BaseTool):
    """
    Tool for generating charts from data.

    This tool creates visualizations from previously queried data
    or from data provided in the request.
    """

    def __init__(self, chart_generator: Optional[ChartGenerator] = None):
        """Initialize with optional chart generator."""
        self.chart_generator = chart_generator or ChartGenerator()
        self._last_data: Optional[pd.DataFrame] = None

    @property
    def name(self) -> str:
        return "generate_chart"

    @property
    def schema(self) -> dict:
        return GENERATE_CHART_SCHEMA

    def set_data(self, data: pd.DataFrame) -> None:
        """Set the data to use for chart generation."""
        self._last_data = data

    def execute(
        self,
        chart_type: str = "horizontal_bar",
        title: str = "",
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        data: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Generate a chart from data.

        Args:
            chart_type: Type of chart to generate
            title: Chart title
            x_column: Column for x-axis
            y_column: Column for y-axis
            data: Optional DataFrame (uses last query data if not provided)

        Returns:
            ToolResult with chart image
        """
        try:
            # Use provided data or fall back to last query data
            chart_data = data if data is not None else self._last_data

            if chart_data is None or chart_data.empty:
                return ToolResult(
                    success=False,
                    error="No data available for chart generation",
                )

            # Infer columns if not specified
            if x_column is None:
                text_cols = chart_data.select_dtypes(include=["object"]).columns
                x_column = text_cols[0] if len(text_cols) > 0 else chart_data.columns[0]

            if y_column is None:
                numeric_cols = chart_data.select_dtypes(include=["number"]).columns
                y_column = (
                    numeric_cols[0]
                    if len(numeric_cols) > 0
                    else chart_data.columns[1]
                )

            # Map chart type string to enum
            chart_type_map = {
                "bar": ChartType.BAR,
                "horizontal_bar": ChartType.HORIZONTAL_BAR,
                "line": ChartType.LINE,
                "pie": ChartType.PIE,
            }
            chart_type_enum = chart_type_map.get(chart_type, ChartType.HORIZONTAL_BAR)

            # Create config
            config = ChartConfig(
                chart_type=chart_type_enum,
                title=title,
                x_column=x_column,
                y_column=y_column,
                max_items=10,
                show_values=True,
            )

            # Generate chart
            chart = self.chart_generator.generate(chart_data, config)

            return ToolResult(
                success=True,
                data={
                    "chart_base64": chart.image_base64,
                    "format": "png",
                    "config": config.to_dict(),
                },
                metadata={"generation_time_ms": chart.generation_time_ms},
            )

        except Exception as e:
            logger.error("GenerateChartTool failed: %s", e)
            return ToolResult(success=False, error=str(e))


class GetSchemaInfoTool(BaseTool):
    """Tool for retrieving database schema information."""

    def __init__(self, schema_discovery: SchemaDiscovery):
        """Initialize with schema discovery component."""
        self.schema_discovery = schema_discovery

    @property
    def name(self) -> str:
        return "get_schema_info"

    @property
    def schema(self) -> dict:
        return GET_SCHEMA_INFO_SCHEMA

    def execute(self, table_name: Optional[str] = None, **kwargs) -> ToolResult:
        """
        Get schema information.

        Args:
            table_name: Optional specific table to get info for

        Returns:
            ToolResult with schema information
        """
        try:
            if table_name:
                schema = self.schema_discovery.get_table_schema(table_name)
                return ToolResult(
                    success=True,
                    data={
                        "table": table_name,
                        "columns": [
                            {
                                "name": col.name,
                                "type": col.data_type,
                                "nullable": col.nullable,
                            }
                            for col in schema.columns
                        ],
                        "row_count": schema.row_count,
                    },
                )
            else:
                tables = self.schema_discovery.discover_tables()
                return ToolResult(
                    success=True,
                    data={"tables": tables},
                )

        except Exception as e:
            logger.error("GetSchemaInfoTool failed: %s", e)
            return ToolResult(success=False, error=str(e))


class SalesInsightToolkit:
    """
    Collection of tools for the SalesInsight agent.

    This class provides all the tools needed for the agent
    to interact with sales data, including query execution,
    chart generation, and schema exploration.
    """

    def __init__(
        self,
        data_source: SnowflakeDataSource,
        sql_generator: NL2SQLGenerator,
        query_validator: QueryValidator,
        prompt_builder: PromptBuilder,
        schema_discovery: SchemaDiscovery,
        chart_generator: Optional[ChartGenerator] = None,
    ):
        """Initialize the toolkit with required components."""
        self.chart_generator = chart_generator or ChartGenerator()

        # Initialize tools
        self.query_sales_data = QuerySalesDataTool(
            data_source=data_source,
            sql_generator=sql_generator,
            query_validator=query_validator,
            prompt_builder=prompt_builder,
            schema_discovery=schema_discovery,
            chart_generator=self.chart_generator,
        )

        self.generate_chart = GenerateChartTool(
            chart_generator=self.chart_generator,
        )

        self.get_schema_info = GetSchemaInfoTool(
            schema_discovery=schema_discovery,
        )

        self._tools = {
            "query_sales_data": self.query_sales_data,
            "generate_chart": self.generate_chart,
            "get_schema_info": self.get_schema_info,
        }

    def get_tool_schemas(self) -> list[dict]:
        """Get all tool schemas for function calling."""
        return [tool.schema for tool in self._tools.values()]

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with given arguments."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        return tool.execute(**kwargs)

    def handle_function_call(
        self,
        function_name: str,
        arguments: str | dict,
    ) -> str:
        """
        Handle a function call from OpenAI function calling.

        Args:
            function_name: Name of the function to call
            arguments: JSON string or dict of arguments

        Returns:
            JSON string response for the function call
        """
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON arguments"})

        result = self.execute_tool(function_name, **arguments)

        # Store data for potential chart generation
        if function_name == "query_sales_data" and result.success:
            data = result.data.get("data")
            if data:
                self.generate_chart.set_data(pd.DataFrame(data))

        return result.to_json()
