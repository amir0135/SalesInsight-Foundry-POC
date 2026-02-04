"""
Chart Generator for SalesInsight POC.

This module provides the core chart generation functionality using
matplotlib and seaborn for creating sales data visualizations.
"""

import base64
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Use non-interactive backend for server-side rendering
matplotlib.use("Agg")

logger = logging.getLogger(__name__)


class ChartType(Enum):
    """Supported chart types."""

    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    LINE = "line"
    PIE = "pie"
    STACKED_BAR = "stacked_bar"
    GROUPED_BAR = "grouped_bar"


@dataclass
class ChartConfig:
    """Configuration for chart generation."""

    chart_type: ChartType = ChartType.BAR
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    x_column: str = ""
    y_column: str = ""
    group_column: Optional[str] = None
    color_palette: str = "viridis"
    figsize: tuple[int, int] = (10, 6)
    show_values: bool = True
    value_format: str = "{:,.0f}"
    sort_values: bool = True
    sort_ascending: bool = False
    max_items: int = 10
    rotation: int = 45
    legend_position: str = "best"
    style: str = "whitegrid"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chart_type": self.chart_type.value,
            "title": self.title,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "group_column": self.group_column,
            "color_palette": self.color_palette,
            "figsize": self.figsize,
            "show_values": self.show_values,
            "max_items": self.max_items,
        }


@dataclass
class GeneratedChart:
    """Result of chart generation."""

    image_base64: str
    image_format: str = "png"
    config: Optional[ChartConfig] = None
    generation_time_ms: float = 0.0
    data_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "image_base64": self.image_base64,
            "image_format": self.image_format,
            "config": self.config.to_dict() if self.config else None,
            "generation_time_ms": self.generation_time_ms,
            "data_summary": self.data_summary,
        }

    def get_data_url(self) -> str:
        """Get data URL for embedding in HTML."""
        return f"data:image/{self.image_format};base64,{self.image_base64}"


class ChartGenerator:
    """
    Generates charts from pandas DataFrames for sales data visualization.

    This class provides a unified interface for creating various chart types
    optimized for sales analytics, including:
    - Ranking charts (top N products, customers)
    - Comparison charts (period over period)
    - Distribution charts (revenue by region)
    """

    # Default color schemes for sales data
    DEFAULT_COLORS = {
        "ranking": ["#2ecc71", "#3498db", "#9b59b6", "#e74c3c", "#f1c40f"],
        "comparison": ["#3498db", "#e74c3c"],
        "categorical": "Set2",
        "sequential": "Blues",
    }

    def __init__(
        self,
        default_style: str = "whitegrid",
        default_palette: str = "viridis",
    ):
        """
        Initialize the chart generator.

        Args:
            default_style: Default seaborn style
            default_palette: Default color palette
        """
        self.default_style = default_style
        self.default_palette = default_palette

        # Set default aesthetics
        sns.set_theme(style=default_style)
        plt.rcParams["figure.dpi"] = 100
        plt.rcParams["savefig.dpi"] = 150
        plt.rcParams["font.size"] = 10

        logger.info("ChartGenerator initialized")

    def generate(
        self,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> GeneratedChart:
        """
        Generate a chart from data using the specified configuration.

        Args:
            data: DataFrame containing the data to visualize
            config: Chart configuration

        Returns:
            GeneratedChart with base64-encoded image
        """
        start_time = datetime.now()

        try:
            # Validate inputs
            self._validate_config(data, config)

            # Prepare data
            prepared_data = self._prepare_data(data, config)

            # Generate chart based on type
            fig = self._create_chart(prepared_data, config)

            # Convert to base64
            image_base64 = self._fig_to_base64(fig)

            # Close figure to free memory
            plt.close(fig)

            # Calculate generation time
            generation_time = (datetime.now() - start_time).total_seconds() * 1000

            # Create data summary
            data_summary = self._create_data_summary(prepared_data, config)

            logger.info(
                "Generated %s chart in %.0fms with %d data points",
                config.chart_type.value,
                generation_time,
                len(prepared_data),
            )

            return GeneratedChart(
                image_base64=image_base64,
                image_format="png",
                config=config,
                generation_time_ms=generation_time,
                data_summary=data_summary,
            )

        except Exception as e:
            logger.error("Chart generation failed: %s", e)
            raise ChartGenerationError(f"Failed to generate chart: {e}") from e

    def _validate_config(self, data: pd.DataFrame, config: ChartConfig) -> None:
        """Validate chart configuration against data."""
        if data.empty:
            raise ChartGenerationError("Cannot generate chart from empty DataFrame")

        if config.x_column and config.x_column not in data.columns:
            raise ChartGenerationError(
                f"X column '{config.x_column}' not found in data"
            )

        if config.y_column and config.y_column not in data.columns:
            raise ChartGenerationError(
                f"Y column '{config.y_column}' not found in data"
            )

    def _prepare_data(
        self,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> pd.DataFrame:
        """Prepare data for charting (sort, limit, etc.)."""
        prepared = data.copy()

        # Sort if configured
        if config.sort_values and config.y_column:
            prepared = prepared.sort_values(
                by=config.y_column,
                ascending=config.sort_ascending,
            )

        # Limit to max items
        if config.max_items and len(prepared) > config.max_items:
            prepared = prepared.head(config.max_items)

        return prepared

    def _create_chart(
        self,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> plt.Figure:
        """Create the matplotlib figure based on chart type."""
        sns.set_theme(style=config.style)

        fig, ax = plt.subplots(figsize=config.figsize)

        chart_creators = {
            ChartType.BAR: self._create_bar_chart,
            ChartType.HORIZONTAL_BAR: self._create_horizontal_bar_chart,
            ChartType.LINE: self._create_line_chart,
            ChartType.PIE: self._create_pie_chart,
            ChartType.STACKED_BAR: self._create_stacked_bar_chart,
            ChartType.GROUPED_BAR: self._create_grouped_bar_chart,
        }

        creator = chart_creators.get(config.chart_type)
        if not creator:
            raise ChartGenerationError(
                f"Unsupported chart type: {config.chart_type}"
            )

        creator(ax, data, config)

        # Apply common styling
        self._apply_styling(ax, config)

        # Adjust layout
        plt.tight_layout()

        return fig

    def _create_bar_chart(
        self,
        ax: plt.Axes,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> None:
        """Create a vertical bar chart."""
        colors = sns.color_palette(config.color_palette, len(data))

        bars = ax.bar(
            data[config.x_column],
            data[config.y_column],
            color=colors,
        )

        # Add value labels if configured
        if config.show_values:
            self._add_bar_labels(ax, bars, config.value_format)

    def _create_horizontal_bar_chart(
        self,
        ax: plt.Axes,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> None:
        """Create a horizontal bar chart (good for rankings)."""
        colors = sns.color_palette(config.color_palette, len(data))

        # Reverse for horizontal bar to show highest at top
        plot_data = data.iloc[::-1]

        bars = ax.barh(
            plot_data[config.x_column],
            plot_data[config.y_column],
            color=colors[::-1],
        )

        # Add value labels
        if config.show_values:
            for bar in bars:
                width = bar.get_width()
                label = config.value_format.format(width)
                ax.annotate(
                    label,
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0),
                    textcoords="offset points",
                    ha="left",
                    va="center",
                    fontsize=9,
                )

    def _create_line_chart(
        self,
        ax: plt.Axes,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> None:
        """Create a line chart for trends."""
        ax.plot(
            data[config.x_column],
            data[config.y_column],
            marker="o",
            linewidth=2,
            markersize=6,
            color=sns.color_palette(config.color_palette)[0],
        )

        # Add value labels at points
        if config.show_values:
            for x, y in zip(
                data[config.x_column], data[config.y_column], strict=False
            ):
                label = config.value_format.format(y)
                ax.annotate(
                    label,
                    xy=(x, y),
                    xytext=(0, 10),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                )

    def _create_pie_chart(
        self,
        ax: plt.Axes,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> None:
        """Create a pie chart for distribution."""
        colors = sns.color_palette(config.color_palette, len(data))

        wedges, texts, autotexts = ax.pie(
            data[config.y_column],
            labels=data[config.x_column],
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
        )

        # Style the text
        for autotext in autotexts:
            autotext.set_fontsize(9)

    def _create_stacked_bar_chart(
        self,
        ax: plt.Axes,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> None:
        """Create a stacked bar chart for composition."""
        if not config.group_column:
            raise ChartGenerationError(
                "group_column required for stacked bar chart"
            )

        # Pivot data for stacking
        pivot_data = data.pivot(
            index=config.x_column,
            columns=config.group_column,
            values=config.y_column,
        ).fillna(0)

        pivot_data.plot(
            kind="bar",
            stacked=True,
            ax=ax,
            colormap=config.color_palette,
        )

    def _create_grouped_bar_chart(
        self,
        ax: plt.Axes,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> None:
        """Create a grouped bar chart for comparison."""
        if not config.group_column:
            raise ChartGenerationError(
                "group_column required for grouped bar chart"
            )

        sns.barplot(
            data=data,
            x=config.x_column,
            y=config.y_column,
            hue=config.group_column,
            ax=ax,
            palette=config.color_palette,
        )

    def _add_bar_labels(
        self,
        ax: plt.Axes,
        bars: Any,
        format_str: str,
    ) -> None:
        """Add value labels on top of bars."""
        for bar in bars:
            height = bar.get_height()
            label = format_str.format(height)
            ax.annotate(
                label,
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    def _apply_styling(self, ax: plt.Axes, config: ChartConfig) -> None:
        """Apply common styling to the chart."""
        # Set title and labels
        if config.title:
            ax.set_title(config.title, fontsize=14, fontweight="bold", pad=15)

        if config.x_label:
            ax.set_xlabel(config.x_label, fontsize=11)

        if config.y_label:
            ax.set_ylabel(config.y_label, fontsize=11)

        # Rotate x-axis labels if needed
        if config.rotation and config.chart_type not in [
            ChartType.HORIZONTAL_BAR,
            ChartType.PIE,
        ]:
            plt.xticks(rotation=config.rotation, ha="right")

        # Format y-axis with thousands separator for large numbers
        if config.chart_type not in [ChartType.PIE]:
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, p: f"{x:,.0f}")
            )

        # Add legend if grouped
        if config.group_column:
            ax.legend(loc=config.legend_position)

        # Remove top and right spines for cleaner look
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    def _fig_to_base64(self, fig: plt.Figure) -> str:
        """Convert matplotlib figure to base64 string."""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    def _create_data_summary(
        self,
        data: pd.DataFrame,
        config: ChartConfig,
    ) -> dict:
        """Create a summary of the data used in the chart."""
        summary = {
            "row_count": len(data),
            "columns_used": [config.x_column, config.y_column],
        }

        if config.y_column and config.y_column in data.columns:
            y_data = data[config.y_column]
            summary["y_stats"] = {
                "min": float(y_data.min()),
                "max": float(y_data.max()),
                "sum": float(y_data.sum()),
                "mean": float(y_data.mean()),
            }

        return summary

    def generate_ranking_chart(
        self,
        data: pd.DataFrame,
        label_column: str,
        value_column: str,
        title: str = "Top Rankings",
        max_items: int = 10,
    ) -> GeneratedChart:
        """
        Generate a ranking chart (horizontal bar) for top N items.

        This is a convenience method for the common "top N by value" use case.

        Args:
            data: DataFrame with ranking data
            label_column: Column containing item labels
            value_column: Column containing values to rank by
            title: Chart title
            max_items: Maximum items to show

        Returns:
            GeneratedChart with ranking visualization
        """
        config = ChartConfig(
            chart_type=ChartType.HORIZONTAL_BAR,
            title=title,
            x_column=label_column,
            y_column=value_column,
            x_label="",
            y_label=value_column,
            max_items=max_items,
            sort_values=True,
            sort_ascending=False,
            color_palette="Blues_r",
            show_values=True,
            figsize=(10, max(6, max_items * 0.5)),
        )

        return self.generate(data, config)

    def generate_comparison_chart(
        self,
        data: pd.DataFrame,
        category_column: str,
        value_column: str,
        group_column: str,
        title: str = "Comparison",
    ) -> GeneratedChart:
        """
        Generate a comparison chart (grouped bar) for comparing groups.

        Args:
            data: DataFrame with comparison data
            category_column: Column for x-axis categories
            value_column: Column for values
            group_column: Column for grouping/comparing
            title: Chart title

        Returns:
            GeneratedChart with comparison visualization
        """
        config = ChartConfig(
            chart_type=ChartType.GROUPED_BAR,
            title=title,
            x_column=category_column,
            y_column=value_column,
            group_column=group_column,
            color_palette=self.DEFAULT_COLORS["comparison"],
            show_values=False,
            figsize=(12, 6),
        )

        return self.generate(data, config)


class ChartGenerationError(Exception):
    """Exception raised when chart generation fails."""

    pass
