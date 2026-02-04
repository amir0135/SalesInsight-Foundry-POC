"""
Chart Generation module for SalesInsight POC.

This module provides visualization capabilities for sales data
using matplotlib and seaborn, with optimized templates for
ranking, comparison, and trend visualizations.
"""

from .chart_generator import (
    ChartGenerator,
    ChartConfig,
    ChartType,
    GeneratedChart,
    ChartGenerationError,
)
from .chart_templates import (
    BarChartTemplate,
    RankingChartTemplate,
    ComparisonChartTemplate,
)

__all__ = [
    # Core generator
    "ChartGenerator",
    "ChartConfig",
    "ChartType",
    "GeneratedChart",
    "ChartGenerationError",
    # Templates
    "BarChartTemplate",
    "RankingChartTemplate",
    "ComparisonChartTemplate",
]
