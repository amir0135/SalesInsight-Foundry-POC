"""
SalesInsight Agent module for natural language sales analytics.

This module provides the AI agent orchestration for processing
natural language queries about sales data, generating SQL,
executing queries, and creating visualizations.
"""

from .sales_insight_agent import (
    SalesInsightAgent,
    SalesInsightConfig,
    SalesInsightResponse,
    SalesInsightError,
)
from .agent_tools import (
    QuerySalesDataTool,
    GenerateChartTool,
    SalesInsightToolkit,
)

__all__ = [
    # Core agent
    "SalesInsightAgent",
    "SalesInsightConfig",
    "SalesInsightResponse",
    "SalesInsightError",
    # Tools
    "QuerySalesDataTool",
    "GenerateChartTool",
    "SalesInsightToolkit",
]
