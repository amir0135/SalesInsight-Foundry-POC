"""Visualization helper for Database query results.

Analyzes query results and suggests appropriate chart types and configurations.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Chart type constants
CHART_TYPES = {
    "bar": "bar",
    "line": "line",
    "pie": "pie",
    "area": "area",
    "table": "table",  # Fallback - just show data table
}


def analyze_data_for_visualization(
    columns: List[str], rows: List[Tuple], question: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Analyze query results and suggest the best visualization.

    Args:
        columns: List of column names
        rows: List of data rows
        question: Original question (for context)

    Returns:
        Visualization configuration dict or None if table is best
    """
    if not columns or not rows or len(rows) < 2:
        return None  # Not enough data for meaningful chart

    # Analyze column types
    column_analysis = _analyze_columns(columns, rows)

    # Determine chart type based on data structure
    chart_config = _suggest_chart_type(column_analysis, columns, rows, question)

    if chart_config:
        # Add the data to the config
        chart_config["data"] = _prepare_chart_data(columns, rows, chart_config)
        logger.info(f"Suggested visualization: {chart_config.get('type', 'none')}")

    return chart_config


def _analyze_columns(columns: List[str], rows: List[Tuple]) -> Dict[str, Dict]:
    """Analyze each column's data type and characteristics."""
    analysis = {}

    for i, col in enumerate(columns):
        col_values = [row[i] for row in rows if row[i] is not None]

        if not col_values:
            analysis[col] = {"type": "unknown", "index": i}
            continue

        # Check if numeric
        numeric_count = sum(1 for v in col_values if _is_numeric(v))
        is_numeric = numeric_count > len(col_values) * 0.8

        # Check if date/time
        is_temporal = _is_temporal_column(col, col_values)

        # Check if categorical (few unique values)
        unique_values = set(str(v) for v in col_values)
        is_categorical = len(unique_values) <= min(15, len(col_values) * 0.5)

        analysis[col] = {
            "type": "numeric" if is_numeric else "temporal" if is_temporal else "categorical" if is_categorical else "text",
            "index": i,
            "unique_count": len(unique_values),
            "sample_values": list(unique_values)[:5],
        }

    return analysis


def _is_numeric(value: Any) -> bool:
    """Check if a value is numeric."""
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.replace(",", "").replace("%", ""))
            return True
        except ValueError:
            return False
    return False


def _is_temporal_column(col_name: str, values: List) -> bool:
    """Check if a column contains temporal data."""
    temporal_keywords = ["date", "time", "day", "month", "year", "week", "hour", "created", "updated", "timestamp"]
    if any(kw in col_name.lower() for kw in temporal_keywords):
        return True

    # Check values for date patterns
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
        r"\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY
        r"\d{4}/\d{2}/\d{2}",  # YYYY/MM/DD
    ]
    sample = values[:10]
    for val in sample:
        if isinstance(val, str):
            for pattern in date_patterns:
                if re.match(pattern, val):
                    return True
    return False


def _suggest_chart_type(
    column_analysis: Dict, columns: List[str], rows: List[Tuple], question: str
) -> Optional[Dict]:
    """Suggest the best chart type based on data analysis."""
    question_lower = question.lower()

    # Count column types
    numeric_cols = [c for c, info in column_analysis.items() if info["type"] == "numeric"]
    categorical_cols = [c for c, info in column_analysis.items() if info["type"] == "categorical"]
    temporal_cols = [c for c, info in column_analysis.items() if info["type"] == "temporal"]

    # Keywords that suggest specific chart types
    trend_keywords = ["trend", "over time", "history", "daily", "weekly", "monthly", "timeline"]
    distribution_keywords = ["distribution", "breakdown", "proportion", "percentage", "share"]
    comparison_keywords = ["compare", "comparison", "top", "most", "highest", "lowest", "rank"]

    # Determine chart type
    if any(kw in question_lower for kw in trend_keywords) and temporal_cols and numeric_cols:
        return {
            "type": CHART_TYPES["line"],
            "xKey": temporal_cols[0],
            "yKeys": numeric_cols[:3],  # Limit to 3 metrics
            "title": _generate_chart_title(question, "Trend"),
        }

    if any(kw in question_lower for kw in distribution_keywords) and len(numeric_cols) == 1 and categorical_cols:
        # Pie chart for single metric distribution
        if len(rows) <= 8:
            return {
                "type": CHART_TYPES["pie"],
                "nameKey": categorical_cols[0],
                "valueKey": numeric_cols[0],
                "title": _generate_chart_title(question, "Distribution"),
            }

    if categorical_cols and numeric_cols:
        # Bar chart for categorical comparisons
        return {
            "type": CHART_TYPES["bar"],
            "xKey": categorical_cols[0],
            "yKeys": numeric_cols[:3],
            "title": _generate_chart_title(question, "Comparison"),
        }

    if temporal_cols and numeric_cols:
        # Area chart for time-based metrics
        return {
            "type": CHART_TYPES["area"],
            "xKey": temporal_cols[0],
            "yKeys": numeric_cols[:3],
            "title": _generate_chart_title(question, "Over Time"),
        }

    if len(numeric_cols) >= 2 and categorical_cols:
        # Multiple metrics - use bar chart
        return {
            "type": CHART_TYPES["bar"],
            "xKey": categorical_cols[0] if categorical_cols else columns[0],
            "yKeys": numeric_cols[:4],
            "title": _generate_chart_title(question, "Summary"),
        }

    # Default: If we have at least one categorical and one numeric, try bar chart
    if len(columns) >= 2 and numeric_cols:
        non_numeric = [c for c in columns if c not in numeric_cols]
        if non_numeric:
            return {
                "type": CHART_TYPES["bar"],
                "xKey": non_numeric[0],
                "yKeys": numeric_cols[:3],
                "title": _generate_chart_title(question, "Data"),
            }

    return None  # Fallback to table only


def _generate_chart_title(question: str, chart_type: str) -> str:
    """Generate a concise chart title from the question."""
    # Remove common question words and shorten
    words_to_remove = ["show", "me", "give", "get", "what", "is", "are", "the", "a", "an", "please", "can", "you"]
    words = question.lower().split()
    title_words = [w for w in words if w not in words_to_remove]
    title = " ".join(title_words[:6]).title()

    if len(title) > 50:
        title = title[:47] + "..."

    return title or f"{chart_type} View"


def _prepare_chart_data(
    columns: List[str], rows: List[Tuple], chart_config: Dict
) -> List[Dict]:
    """Prepare data in the format expected by recharts."""
    data = []

    for row in rows[:100]:  # Limit rows for visualization
        row_dict = {}
        for i, col in enumerate(columns):
            value = row[i]
            # Convert numeric strings to numbers for charting
            if _is_numeric(value):
                if isinstance(value, str):
                    value = float(value.replace(",", "").replace("%", ""))
                row_dict[col] = value
            else:
                row_dict[col] = str(value) if value is not None else ""
        data.append(row_dict)

    return data


def get_chart_colors() -> List[str]:
    """Return a list of chart colors for consistent styling."""
    return [
        "#0078D4",  # Microsoft Blue
        "#107C10",  # Green
        "#FFB900",  # Yellow
        "#D83B01",  # Orange
        "#8764B8",  # Purple
        "#00B7C3",  # Teal
        "#E74856",  # Red
        "#567C73",  # Sage
    ]
