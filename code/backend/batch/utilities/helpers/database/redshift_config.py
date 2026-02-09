"""Configuration for Redshift/PostgreSQL table and column allowlists.

This matches the actual Database data schema from CSV exports.
"""

# Allowlist configuration matching actual CSV data
# Only these tables and columns can be queried

ALLOWED_TABLES = {
    "orderhistoryline": [
        "id",
        "domainid",
        "orderhistoryid",
        "ean",
        "softdeleted",
        "ordertype",
        "requesteddeliverydate",
        "confirmeddeliverydate",
        "requestquantity",
        "requestquantitypieces",
        "confirmeddeliveryquantity",
        "confirmeddeliveryquantitypieces",
        "currencyisoalpha3",
        "unitretailprice",
        "unitgrossprice",
        "unitnetprice",
        "stylenumber",
        "status",
        "skutype",
        "discount",
        "estimateddeliverydate",
        "brandid",
        "productlineid",
        "note",
    ],
}

# Table aliases for backward compatibility
TABLE_ALIASES = {
    "orders": "orderhistoryline",
    "order_history": "orderhistoryline",
    "sales": "orderhistoryline",
    "products": "orderhistoryline",
}


def resolve_table_name(table_name: str) -> str:
    """Resolve table aliases to actual table names."""
    return TABLE_ALIASES.get(table_name, table_name)


def validate_table(table_name: str) -> bool:
    """Validate that table is in allowlist."""
    resolved = resolve_table_name(table_name)
    return resolved in ALLOWED_TABLES


def validate_columns(table_name: str, columns: list) -> bool:
    """Validate that all columns are in allowlist for the table."""
    resolved = resolve_table_name(table_name)
    if resolved not in ALLOWED_TABLES:
        return False

    allowed = set(ALLOWED_TABLES[resolved])
    requested = set(columns)

    return requested.issubset(allowed)


def get_allowed_columns(table_name: str) -> list:
    """Get allowed columns for a table."""
    resolved = resolve_table_name(table_name)
    return ALLOWED_TABLES.get(resolved, [])


# Schema description for LLM SQL generation
SCHEMA_DESCRIPTION = {
    "orderhistoryline": {
        "description": "Sales order history with product details, pricing, quantities, and delivery information",
        "common_uses": [
            "Sales analysis",
            "Revenue reporting",
            "Order status tracking",
            "Product performance",
            "Delivery analysis",
        ],
        "key_columns": {
            "stylenumber": "Product style number (e.g., 30001010, 30001009) - use for product grouping",
            "status": "Order status (OPEN, ALLOCATED) - use for filtering",
            "currencyisoalpha3": "Currency code (EUR, USD)",
            "unitnetprice": "Net price per unit - use for revenue calculations",
            "unitgrossprice": "Gross price per unit",
            "unitretailprice": "Retail price per unit",
            "requestquantity": "Requested quantity",
            "requestquantitypieces": "Requested quantity in pieces",
            "confirmeddeliveryquantity": "Confirmed delivery quantity",
            "requesteddeliverydate": "Requested delivery date (use for time filtering)",
            "estimateddeliverydate": "Estimated delivery date",
            "skutype": "SKU type (FreeAssortment, Assortment)",
            "discount": "Discount percentage applied",
            "brandid": "Brand identifier (e.g., B_21)",
            "productlineid": "Product line identifier (e.g., B_2102)",
            "softdeleted": "Whether order was soft deleted (true/false)",
            "ean": "Product EAN barcode",
        },
    },
}

# Keywords that map to tables for smart schema retrieval
TABLE_KEYWORDS = {
    "orderhistoryline": [
        "order", "orders", "sales", "revenue", "product", "products",
        "price", "pricing", "quantity", "delivery", "status", "discount",
        "sku", "brand", "style", "currency", "eur", "usd", "allocated",
        "open", "top", "best", "worst", "total", "count", "how many"
    ],
}


def get_relevant_tables(question: str) -> list:
    """
    Determine which tables are relevant based on question keywords.

    Args:
        question: The natural language question

    Returns:
        List of relevant table names, or all tables if no match
    """
    # For single-table setup, always return the main table
    return list(ALLOWED_TABLES.keys())


def get_schema_for_prompt(question: str = None) -> str:
    """
    Generate schema description for LLM prompt.

    Args:
        question: Optional question to filter relevant tables.
                  If None, includes all tables.

    Returns:
        Schema description string for the prompt
    """
    # Determine which tables to include
    if question:
        tables_to_include = get_relevant_tables(question)
    else:
        tables_to_include = list(ALLOWED_TABLES.keys())

    lines = ["Available tables and columns:\n"]
    for table in tables_to_include:
        columns = ALLOWED_TABLES.get(table, [])
        desc = SCHEMA_DESCRIPTION.get(table, {}).get("description", "")
        lines.append(f"### {table}")
        if desc:
            lines.append(f"Description: {desc}")
        lines.append(f"Columns: {', '.join(columns)}")
        key_cols = SCHEMA_DESCRIPTION.get(table, {}).get("key_columns", {})
        if key_cols:
            lines.append("Key columns:")
            for col, col_desc in key_cols.items():
                lines.append(f"  - {col}: {col_desc}")
        lines.append("")
    return "\n".join(lines)


# System prompt for SQL generation (fallback if file not found)
SQL_GENERATION_SYSTEM_PROMPT = """You are a SQL query generator for a sales order data warehouse.
Your task is to convert natural language questions into valid PostgreSQL SQL queries.

{schema}

TABLE NAME (use exactly this):
- orderhistoryline: Contains all sales order data

RULES:
1. ONLY generate SELECT queries - never INSERT, UPDATE, DELETE, DROP, etc.
2. Return ONLY the SQL query, no explanations or markdown.
3. Use lowercase for column names.
4. Current date is: {current_date}

Examples:
- "What are the top 10 products by revenue?" ->
SELECT stylenumber, SUM(unitnetprice * requestquantity) as revenue FROM orderhistoryline WHERE softdeleted = false GROUP BY stylenumber ORDER BY revenue DESC LIMIT 10
"""


def get_sql_generation_prompt() -> str:
    """
    Load SQL generation prompt from file with fallback to hardcoded default.

    Prompt is loaded from:
    1. prompts/sql_generation.txt file (preferred, easy to edit)
    2. SQL_GENERATION_SYSTEM_PROMPT constant (fallback)

    Returns:
        str: The SQL generation system prompt
    """
    import os

    prompt_file = os.path.join(
        os.path.dirname(__file__), "prompts", "sql_generation.txt"
    )

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fall back to hardcoded default if file not found
        return SQL_GENERATION_SYSTEM_PROMPT


# Dangerous SQL patterns to block
DANGEROUS_PATTERNS = [
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b",
    r";",  # No multiple statements
    r"--",  # No SQL comments
    r"/\*",  # No block comments
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bINTO\s+OUTFILE\b",
    r"\bINTO\s+DUMPFILE\b",
]


def validate_generated_sql(sql_query: str) -> tuple:
    """
    Validate that generated SQL is safe to execute.

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    import re

    sql_upper = sql_query.upper().strip()

    # Must be a SELECT query
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, sql_query, re.IGNORECASE):
            return False, "Query contains disallowed pattern"

    # Validate tables used
    all_tables = set(ALLOWED_TABLES.keys()) | set(TABLE_ALIASES.keys())
    from_match = re.search(r"\bFROM\s+(\w+)", sql_query, re.IGNORECASE)
    join_matches = re.findall(r"\bJOIN\s+(\w+)", sql_query, re.IGNORECASE)

    tables_used = []
    if from_match:
        tables_used.append(from_match.group(1).lower())
    tables_used.extend([t.lower() for t in join_matches])

    for table in tables_used:
        if table not in all_tables:
            return False, f"Table '{table}' is not in the allowed list"

    return True, None


def add_limit_if_missing(sql_query: str, max_rows: int = 100) -> str:
    """Add LIMIT clause if not present."""
    import re

    if not re.search(r"\bLIMIT\s+\d+", sql_query, re.IGNORECASE):
        return f"{sql_query.rstrip()} LIMIT {max_rows}"
    return sql_query
