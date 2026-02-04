import ssl
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pandas as pd
import pytest
import trustme


# =============================================================================
# SSL/HTTPS Fixtures (existing)
# =============================================================================


@pytest.fixture(scope="session")
def ca():
    """
    This fixture is required to run the http mock server with SSL.
    https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server
    """
    return trustme.CA()


@pytest.fixture(scope="session")
def httpserver_ssl_context(ca):
    """
    This fixture is required to run the http mock server with SSL.
    https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    localhost_cert = ca.issue_cert("localhost")
    localhost_cert.configure_cert(context)
    return context


@pytest.fixture(scope="session")
def httpclient_ssl_context(ca):
    """
    This fixture is required to run the http mock server with SSL.
    https://pytest-httpserver.readthedocs.io/en/latest/howto.html#running-an-https-server
    """
    with ca.cert_pem.tempfile() as ca_temp_path:
        return ssl.create_default_context(cafile=ca_temp_path)


# =============================================================================
# SalesInsight POC - Snowflake Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_snowflake_connection():
    """Mock Snowflake connection for unit tests."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_snowflake_cursor(mock_snowflake_connection):
    """Mock Snowflake cursor with configurable results."""
    return mock_snowflake_connection.cursor()


@pytest.fixture
def sample_order_history_data() -> List[Dict[str, Any]]:
    """Sample OrderHistoryLine data for testing."""
    return [
        {
            "OrderID": "ORD-001",
            "OrderLineNumber": 1,
            "StyleCode": "STYLE-001",
            "StyleName": "Classic Dress",
            "ColorCode": "BLK",
            "ColorName": "Black",
            "VariantCode": "M",
            "Quantity": 100,
            "NetINV": 5000.00,
            "CustomerCode": "CUST-001",
            "CustomerName": "Galeries Lafayette Paris",
            "Market": "France",
            "Country": "France",
            "Brand": "Brand A",
            "Category": "Dresses",
            "Collection": "COL1 2025",
            "FiscalYear": "FY 25/26",
            "DeliveryMonth": "2025-09",
        },
        {
            "OrderID": "ORD-002",
            "OrderLineNumber": 1,
            "StyleCode": "STYLE-042",
            "StyleName": "Summer Blouse",
            "ColorCode": "WHT",
            "ColorName": "White",
            "VariantCode": "S",
            "Quantity": 75,
            "NetINV": 3750.00,
            "CustomerCode": "CUST-002",
            "CustomerName": "El Corte Inglés",
            "Market": "Spain",
            "Country": "Spain",
            "Brand": "Brand B",
            "Category": "Tops",
            "Collection": "COL1 2025",
            "FiscalYear": "FY 25/26",
            "DeliveryMonth": "2025-10",
        },
        {
            "OrderID": "ORD-003",
            "OrderLineNumber": 1,
            "StyleCode": "STYLE-103",
            "StyleName": "Evening Gown",
            "ColorCode": "RED",
            "ColorName": "Red",
            "VariantCode": "L",
            "Quantity": 50,
            "NetINV": 7500.00,
            "CustomerCode": "CUST-003",
            "CustomerName": "Harrods",
            "Market": "UK",
            "Country": "United Kingdom",
            "Brand": "Brand A",
            "Category": "Dresses",
            "Collection": "COL2 2025",
            "FiscalYear": "FY 25/26",
            "DeliveryMonth": "2025-11",
        },
    ]


@pytest.fixture
def sample_order_history_df(sample_order_history_data) -> pd.DataFrame:
    """Sample OrderHistoryLine DataFrame for testing."""
    return pd.DataFrame(sample_order_history_data)


@pytest.fixture
def sample_aggregated_sales_df() -> pd.DataFrame:
    """Sample aggregated sales data for chart testing."""
    return pd.DataFrame(
        {
            "StyleName": [
                "Classic Dress",
                "Summer Blouse",
                "Evening Gown",
                "Casual Top",
                "Winter Coat",
            ],
            "TotalQuantity": [2450, 1890, 1650, 1200, 980],
            "TotalTurnover": [125000.00, 89500.00, 165000.00, 48000.00, 147000.00],
        }
    )


@pytest.fixture
def sample_schema_info() -> Dict[str, Any]:
    """Sample schema information for OrderHistoryLine table."""
    return {
        "tables": [
            {
                "name": "OrderHistoryLine",
                "columns": [
                    {"name": "OrderID", "type": "VARCHAR", "nullable": False},
                    {"name": "StyleCode", "type": "VARCHAR", "nullable": False},
                    {"name": "StyleName", "type": "VARCHAR", "nullable": False},
                    {"name": "ColorCode", "type": "VARCHAR", "nullable": True},
                    {"name": "ColorName", "type": "VARCHAR", "nullable": True},
                    {"name": "VariantCode", "type": "VARCHAR", "nullable": True},
                    {"name": "Quantity", "type": "INTEGER", "nullable": False},
                    {"name": "NetINV", "type": "DECIMAL(18,2)", "nullable": False},
                    {"name": "CustomerCode", "type": "VARCHAR", "nullable": False},
                    {"name": "CustomerName", "type": "VARCHAR", "nullable": False},
                    {"name": "Market", "type": "VARCHAR", "nullable": False},
                    {"name": "Country", "type": "VARCHAR", "nullable": False},
                    {"name": "Brand", "type": "VARCHAR", "nullable": False},
                    {"name": "Category", "type": "VARCHAR", "nullable": False},
                    {"name": "Collection", "type": "VARCHAR", "nullable": True},
                    {"name": "FiscalYear", "type": "VARCHAR", "nullable": True},
                    {"name": "DeliveryMonth", "type": "VARCHAR", "nullable": True},
                ],
                "row_count": 50000,
            }
        ],
        "last_refreshed": datetime.now().isoformat(),
    }


# =============================================================================
# SalesInsight POC - GPT/LLM Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_gpt_sql_response() -> Dict[str, Any]:
    """Mock GPT-4o response for SQL generation."""
    return {
        "sql": """
            SELECT StyleCode, StyleName, SUM(Quantity) AS TotalQuantity, SUM(NetINV) AS TotalTurnover
            FROM OrderHistoryLine
            WHERE Market = %(market)s
            GROUP BY StyleCode, StyleName
            ORDER BY TotalQuantity DESC
            LIMIT 10
        """,
        "explanation": "This query retrieves the top 10 best-selling styles in the specified market.",
        "parameters": {"market": "France"},
    }


@pytest.fixture
def mock_azure_openai_client():
    """Mock Azure OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "sql": "SELECT StyleCode, StyleName, SUM(Quantity) AS TotalQuantity FROM OrderHistoryLine GROUP BY StyleCode, StyleName ORDER BY TotalQuantity DESC LIMIT 10",
        "explanation": "Top 10 best sold styles by quantity",
        "parameters": {}
    }"""
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# =============================================================================
# SalesInsight POC - Visualization Fixtures
# =============================================================================


@pytest.fixture
def sample_chart_config() -> Dict[str, Any]:
    """Sample chart configuration for testing."""
    return {
        "chart_type": "horizontal_bar",
        "x_column": "StyleName",
        "y_column": "TotalQuantity",
        "title": "Top Selling Styles",
        "x_label": "Style",
        "y_label": "Units Sold",
        "color_palette": "viridis",
        "max_items": 10,
        "figure_size": (10, 6),
    }

