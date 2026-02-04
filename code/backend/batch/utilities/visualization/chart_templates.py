"""
Chart Templates for Sales Data Visualization.

This module provides specialized chart templates optimized for
common sales analytics visualizations like rankings, comparisons,
and period-over-period analysis.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .chart_generator import ChartConfig, ChartGenerator, ChartType, GeneratedChart

logger = logging.getLogger(__name__)


class BaseChartTemplate(ABC):
    """Abstract base class for chart templates."""

    def __init__(self, generator: Optional[ChartGenerator] = None):
        """Initialize with optional generator."""
        self.generator = generator or ChartGenerator()

    @abstractmethod
    def generate(self, data: pd.DataFrame, **kwargs) -> GeneratedChart:
        """Generate chart from data."""
        ...

    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate that data has required columns."""
        ...


@dataclass
class RankingChartConfig:
    """Configuration for ranking charts."""

    label_column: str
    value_column: str
    title: str = "Top Rankings"
    subtitle: Optional[str] = None
    max_items: int = 10
    show_rank_numbers: bool = True
    color_gradient: bool = True
    value_prefix: str = ""
    value_suffix: str = ""
    highlight_top: int = 3


class RankingChartTemplate(BaseChartTemplate):
    """
    Template for ranking visualizations.

    Optimized for showing "Top N by value" scenarios common in sales:
    - Top products by revenue
    - Top customers by turnover
    - Top regions by sales volume
    """

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data has required columns."""
        return len(data) > 0

    def generate(
        self,
        data: pd.DataFrame,
        label_column: str,
        value_column: str,
        title: str = "Top Rankings",
        max_items: int = 10,
        **kwargs,
    ) -> GeneratedChart:
        """
        Generate a ranking chart.

        Args:
            data: DataFrame with ranking data
            label_column: Column containing item labels
            value_column: Column containing values to rank by
            title: Chart title
            max_items: Maximum items to show
            **kwargs: Additional configuration options

        Returns:
            GeneratedChart with ranking visualization
        """
        if not self.validate_data(data):
            raise ValueError("Data validation failed")

        config = RankingChartConfig(
            label_column=label_column,
            value_column=value_column,
            title=title,
            max_items=max_items,
            **kwargs,
        )

        return self._create_ranking_chart(data, config)

    def _create_ranking_chart(
        self,
        data: pd.DataFrame,
        config: RankingChartConfig,
    ) -> GeneratedChart:
        """Create the ranking chart with enhanced styling."""
        # Prepare data
        plot_data = (
            data[[config.label_column, config.value_column]]
            .sort_values(config.value_column, ascending=False)
            .head(config.max_items)
        )

        # Create figure
        fig_height = max(6, config.max_items * 0.6)
        fig, ax = plt.subplots(figsize=(12, fig_height))

        # Set style
        sns.set_theme(style="whitegrid")

        # Create color gradient
        if config.color_gradient:
            colors = self._create_gradient_colors(len(plot_data))
        else:
            colors = sns.color_palette("Blues_r", len(plot_data))

        # Reverse for horizontal bar (highest at top)
        plot_data_reversed = plot_data.iloc[::-1]
        colors_reversed = colors[::-1]

        # Create bars
        bars = ax.barh(
            plot_data_reversed[config.label_column],
            plot_data_reversed[config.value_column],
            color=colors_reversed,
            edgecolor="white",
            linewidth=0.5,
        )

        # Add value labels
        max_value = plot_data[config.value_column].max()
        for i, bar in enumerate(bars):
            width = bar.get_width()
            label = f"{config.value_prefix}{width:,.0f}{config.value_suffix}"

            # Position label inside or outside based on bar width
            if width > max_value * 0.3:
                x_pos = width - max_value * 0.02
                ha = "right"
                color = "white"
            else:
                x_pos = width + max_value * 0.01
                ha = "left"
                color = "black"

            ax.annotate(
                label,
                xy=(x_pos, bar.get_y() + bar.get_height() / 2),
                ha=ha,
                va="center",
                fontsize=10,
                fontweight="bold",
                color=color,
            )

        # Add rank numbers if configured
        if config.show_rank_numbers:
            for i, (_, row) in enumerate(plot_data_reversed.iterrows()):
                rank = len(plot_data) - i
                ax.annotate(
                    f"#{rank}",
                    xy=(-max_value * 0.02, i),
                    ha="right",
                    va="center",
                    fontsize=9,
                    fontweight="bold",
                    color="#666666",
                )

        # Styling
        ax.set_title(
            config.title,
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        if config.subtitle:
            ax.text(
                0.5, 1.02,
                config.subtitle,
                transform=ax.transAxes,
                ha="center",
                fontsize=11,
                color="#666666",
            )

        ax.set_xlabel(config.value_column, fontsize=11)
        ax.set_ylabel("")

        # Clean up spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)

        # Format x-axis
        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f"{x:,.0f}")
        )

        plt.tight_layout()

        # Convert to base64
        image_base64 = self.generator._fig_to_base64(fig)
        plt.close(fig)

        return GeneratedChart(
            image_base64=image_base64,
            image_format="png",
            data_summary={
                "top_item": plot_data[config.label_column].iloc[0],
                "top_value": float(plot_data[config.value_column].iloc[0]),
                "total": float(plot_data[config.value_column].sum()),
                "count": len(plot_data),
            },
        )

    def _create_gradient_colors(self, n: int) -> list:
        """Create a gradient color palette."""
        # Gold to blue gradient for rankings
        base_colors = [
            "#FFD700",  # Gold for #1
            "#C0C0C0",  # Silver for #2
            "#CD7F32",  # Bronze for #3
        ]

        if n <= 3:
            return base_colors[:n]

        # Extend with blue gradient for remaining
        remaining = n - 3
        blues = sns.color_palette("Blues_r", remaining + 2)[2:]
        return base_colors + list(blues)


@dataclass
class ComparisonChartConfig:
    """Configuration for comparison charts."""

    category_column: str
    value_column: str
    group_column: str
    title: str = "Comparison"
    colors: Optional[list[str]] = None
    show_percent_change: bool = True


class ComparisonChartTemplate(BaseChartTemplate):
    """
    Template for comparison visualizations.

    Optimized for period-over-period or group comparisons:
    - Q1 vs Q2 sales
    - Current year vs Previous year
    - Region A vs Region B
    """

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data has required columns."""
        return len(data) > 0

    def generate(
        self,
        data: pd.DataFrame,
        category_column: str,
        value_column: str,
        group_column: str,
        title: str = "Comparison",
        **kwargs,
    ) -> GeneratedChart:
        """
        Generate a comparison chart.

        Args:
            data: DataFrame with comparison data
            category_column: Column for categories (x-axis)
            value_column: Column for values
            group_column: Column for groups to compare
            title: Chart title
            **kwargs: Additional configuration

        Returns:
            GeneratedChart with comparison visualization
        """
        if not self.validate_data(data):
            raise ValueError("Data validation failed")

        config = ComparisonChartConfig(
            category_column=category_column,
            value_column=value_column,
            group_column=group_column,
            title=title,
            **kwargs,
        )

        return self._create_comparison_chart(data, config)

    def _create_comparison_chart(
        self,
        data: pd.DataFrame,
        config: ComparisonChartConfig,
    ) -> GeneratedChart:
        """Create the comparison chart."""
        fig, ax = plt.subplots(figsize=(12, 7))
        sns.set_theme(style="whitegrid")

        # Default colors for comparison
        colors = config.colors or ["#3498db", "#e74c3c", "#2ecc71", "#9b59b6"]

        # Create grouped bar chart
        groups = data[config.group_column].unique()
        n_groups = len(groups)
        n_categories = data[config.category_column].nunique()

        x = range(n_categories)
        width = 0.8 / n_groups

        for i, group in enumerate(groups):
            group_data = data[data[config.group_column] == group]
            offset = (i - n_groups / 2 + 0.5) * width

            bars = ax.bar(
                [xi + offset for xi in x],
                group_data[config.value_column],
                width,
                label=str(group),
                color=colors[i % len(colors)],
                edgecolor="white",
                linewidth=0.5,
            )

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.annotate(
                    f"{height:,.0f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

        # Set x-axis labels
        categories = data[config.category_column].unique()
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha="right")

        # Styling
        ax.set_title(config.title, fontsize=16, fontweight="bold", pad=20)
        ax.set_ylabel(config.value_column, fontsize=11)
        ax.legend(title=config.group_column, loc="upper right")

        # Format y-axis
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f"{x:,.0f}")
        )

        # Clean spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        plt.tight_layout()

        # Convert to base64
        image_base64 = self.generator._fig_to_base64(fig)
        plt.close(fig)

        # Calculate summary statistics
        summary = {"groups": list(groups), "totals": {}}
        for group in groups:
            group_total = data[data[config.group_column] == group][
                config.value_column
            ].sum()
            summary["totals"][str(group)] = float(group_total)

        return GeneratedChart(
            image_base64=image_base64,
            image_format="png",
            data_summary=summary,
        )


class BarChartTemplate(BaseChartTemplate):
    """
    General-purpose bar chart template.

    A flexible template for creating bar charts with various
    configuration options.
    """

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data has required columns."""
        return len(data) > 0

    def generate(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        title: str = "",
        horizontal: bool = False,
        color_palette: str = "viridis",
        max_items: int = 20,
        **kwargs,
    ) -> GeneratedChart:
        """
        Generate a bar chart.

        Args:
            data: DataFrame with chart data
            x_column: Column for x-axis
            y_column: Column for y-axis values
            title: Chart title
            horizontal: Whether to create horizontal bars
            color_palette: Seaborn color palette name
            max_items: Maximum number of bars
            **kwargs: Additional configuration

        Returns:
            GeneratedChart
        """
        chart_type = ChartType.HORIZONTAL_BAR if horizontal else ChartType.BAR

        config = ChartConfig(
            chart_type=chart_type,
            title=title,
            x_column=x_column,
            y_column=y_column,
            x_label=kwargs.get("x_label", x_column),
            y_label=kwargs.get("y_label", y_column),
            color_palette=color_palette,
            max_items=max_items,
            show_values=kwargs.get("show_values", True),
            sort_values=kwargs.get("sort_values", True),
            figsize=kwargs.get("figsize", (10, 6)),
        )

        return self.generator.generate(data, config)
