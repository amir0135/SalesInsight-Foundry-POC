# Data Model: SalesInsight AI Agent

**Feature**: 001-salesinsight-agent  
**Date**: 2026-02-04  
**Status**: Draft

---

## 1. Primary Data Source: OrderHistoryLine

### 1.1 Table Schema (Snowflake)

Based on the 50K row sample CSV provided, the OrderHistoryLine table contains sales transaction data:

| Column Name | Data Type | Nullable | Description |
|-------------|-----------|----------|-------------|
| OrderID | VARCHAR | No | Unique order identifier |
| OrderLineNumber | INTEGER | No | Line number within order |
| OrderDate | DATE | No | Date order was placed |
| DeliveryMonth | VARCHAR | Yes | Expected delivery month (e.g., "2025-03") |
| FiscalYear | VARCHAR | Yes | Fiscal year identifier (e.g., "FY 25/26") |
| StyleCode | VARCHAR | No | Product style code |
| StyleName | VARCHAR | No | Product style description |
| ColorCode | VARCHAR | Yes | Color code |
| ColorName | VARCHAR | Yes | Color description |
| VariantCode | VARCHAR | Yes | Size/variant code |
| VariantName | VARCHAR | Yes | Size/variant description |
| Quantity | INTEGER | No | Quantity ordered |
| UnitPrice | DECIMAL(18,2) | No | Unit price |
| NetINV | DECIMAL(18,2) | No | Net invoice amount (turnover) |
| Currency | VARCHAR | Yes | Currency code (default: EUR) |
| CustomerCode | VARCHAR | No | Customer identifier |
| CustomerName | VARCHAR | No | Customer company name |
| HoldingCode | VARCHAR | Yes | Parent holding company code |
| HoldingName | VARCHAR | Yes | Parent holding company name |
| Market | VARCHAR | No | Market/region code |
| Country | VARCHAR | No | Country name |
| Brand | VARCHAR | No | Brand name |
| Category | VARCHAR | No | Product category |
| SubCategory | VARCHAR | Yes | Product subcategory |
| Collection | VARCHAR | Yes | Collection code (e.g., "COL1 2025") |
| Season | VARCHAR | Yes | Season identifier |

### 1.2 Sample Data Queries

```sql
-- Count by market
SELECT Market, COUNT(*) as Orders, SUM(NetINV) as Turnover
FROM OrderHistoryLine
GROUP BY Market
ORDER BY Turnover DESC;

-- Best sold styles
SELECT StyleCode, StyleName, SUM(Quantity) as TotalQty, SUM(NetINV) as Turnover
FROM OrderHistoryLine
GROUP BY StyleCode, StyleName
ORDER BY TotalQty DESC
LIMIT 10;

-- Collection turnover by market
SELECT Market, Collection, SUM(NetINV) as Turnover
FROM OrderHistoryLine
WHERE Collection = 'COL1 2025'
GROUP BY Market, Collection
ORDER BY Turnover DESC;
```

### 1.3 Business Glossary Mapping

| Business Term | SQL Mapping |
|---------------|-------------|
| Turnover | `SUM(NetINV)` |
| Best sold | `ORDER BY SUM(Quantity) DESC` or `ORDER BY SUM(NetINV) DESC` |
| Revenue | `SUM(NetINV)` |
| Units sold | `SUM(Quantity)` |
| Average order value | `AVG(NetINV)` |
| FY 25/26 | `FiscalYear = 'FY 25/26'` |
| This year | `YEAR(OrderDate) = 2026` |

---

## 2. Application Entities

### 2.1 QuerySession

Tracks user interaction sessions for context and history.

```python
@dataclass
class QuerySession:
    session_id: str                    # UUID
    user_id: Optional[str]             # For future auth
    created_at: datetime
    last_activity: datetime
    conversation_history: List[Message]
    
@dataclass
class Message:
    role: str                          # "user" | "assistant"
    content: str                       # Text content
    timestamp: datetime
    metadata: Optional[Dict]           # Query details, timing
```

### 2.2 QueryRequest

Represents an incoming natural language query.

```python
@dataclass
class QueryRequest:
    session_id: str
    question: str
    conversation_history: List[Message]
    include_visualization: bool = True
```

### 2.3 QueryResponse

Represents the agent's response.

```python
@dataclass
class QueryResponse:
    answer: str                        # Natural language response
    chart: Optional[str]               # Base64 encoded image
    data_preview: Optional[List[Dict]] # Sample data rows
    sql_executed: Optional[str]        # For debugging (optional)
    metadata: ResponseMetadata

@dataclass
class ResponseMetadata:
    query_type: str                    # "aggregation" | "list" | "comparison"
    execution_time_ms: int
    rows_returned: int
    has_visualization: bool
    sources: List[str]                 # Tables used
```

### 2.4 ChartConfig

Configuration for chart generation.

```python
@dataclass
class ChartConfig:
    chart_type: str                    # "bar" | "horizontal_bar" | "grouped_bar"
    x_column: str
    y_column: str
    title: str
    x_label: Optional[str]
    y_label: Optional[str]
    color_palette: str = "viridis"
    max_items: int = 10
    figure_size: Tuple[int, int] = (10, 6)
```

### 2.5 SchemaCache

Cached schema information for query generation.

```python
@dataclass
class SchemaCache:
    tables: Dict[str, TableSchema]
    last_refreshed: datetime
    ttl_seconds: int = 300

@dataclass
class TableSchema:
    name: str
    columns: List[ColumnSchema]
    row_count: Optional[int]

@dataclass
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool
    description: Optional[str]
    sample_values: Optional[List[str]]  # For context
```

### 2.6 AllowlistConfig

Security configuration for SQL validation.

```python
@dataclass
class AllowlistConfig:
    allowed_tables: List[str]
    allowed_columns: Dict[str, List[str]]  # table -> columns
    blocked_keywords: List[str]
    max_result_rows: int = 1000
    query_timeout_seconds: int = 30
```

---

## 3. API Contracts

### 3.1 Sales Query Endpoint

**POST** `/api/sales/query`

**Request Body**:
```json
{
  "question": "What are the best sold styles in France this year?",
  "session_id": "uuid-here",
  "conversation_history": [],
  "include_visualization": true
}
```

**Response Body**:
```json
{
  "answer": "The top 5 best sold styles in France for 2026 are:\n\n1. **STYLE-001** (Classic Dress) - 2,450 units, €125,000\n2. **STYLE-042** (Summer Blouse) - 1,890 units, €89,500\n...",
  "chart": "data:image/png;base64,iVBORw0KGgoAAAANSUhE...",
  "data_preview": [
    {"StyleCode": "STYLE-001", "StyleName": "Classic Dress", "Quantity": 2450, "Turnover": 125000},
    {"StyleCode": "STYLE-042", "StyleName": "Summer Blouse", "Quantity": 1890, "Turnover": 89500}
  ],
  "metadata": {
    "query_type": "aggregation",
    "execution_time_ms": 1250,
    "rows_returned": 5,
    "has_visualization": true,
    "sources": ["OrderHistoryLine"]
  }
}
```

**Error Response**:
```json
{
  "error": {
    "code": "QUERY_FAILED",
    "message": "Unable to process your query. Please try rephrasing.",
    "details": "SQL validation failed: table 'Users' not in allowlist"
  }
}
```

### 3.2 Schema Endpoint

**GET** `/api/sales/schema`

**Response Body**:
```json
{
  "tables": [
    {
      "name": "OrderHistoryLine",
      "columns": [
        {"name": "StyleCode", "type": "VARCHAR", "description": "Product style code"},
        {"name": "StyleName", "type": "VARCHAR", "description": "Product style description"},
        ...
      ],
      "row_count": 50000
    }
  ],
  "last_refreshed": "2026-02-04T10:30:00Z"
}
```

---

## 4. Entity Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                        Query Flow                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Input                                                     │
│       │                                                          │
│       ▼                                                          │
│   QueryRequest ──────► AI Foundry Agent                         │
│       │                    │                                     │
│       │                    ▼                                     │
│       │               NL2SQL Engine                              │
│       │                    │                                     │
│       │                    ▼                                     │
│       │               SQL Validator ◄── AllowlistConfig         │
│       │                    │                                     │
│       │                    ▼                                     │
│       │               Query Executor                             │
│       │                    │                                     │
│       │                    ▼                                     │
│       │              Snowflake DB                                │
│       │            (OrderHistoryLine)                            │
│       │                    │                                     │
│       │                    ▼                                     │
│       │              DataFrame Result                            │
│       │                    │                                     │
│       │        ┌──────────┴──────────┐                          │
│       │        ▼                      ▼                          │
│       │   ChartGenerator      Response Generator                 │
│       │        │                      │                          │
│       │        ▼                      ▼                          │
│       │   Chart Image         Natural Language                   │
│       │        │                      │                          │
│       │        └──────────┬──────────┘                          │
│       │                   ▼                                      │
│       └──────────► QueryResponse                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Data Validation Rules

### 5.1 Input Validation

| Field | Rule |
|-------|------|
| question | Required, 1-1000 characters, no SQL keywords |
| session_id | Optional, valid UUID format |
| include_visualization | Boolean, defaults to true |

### 5.2 Output Validation

| Field | Rule |
|-------|------|
| answer | Always present, max 5000 characters |
| chart | Base64 PNG, max 500KB |
| data_preview | Max 10 rows, sanitized values |
| metadata.execution_time_ms | Non-negative integer |

### 5.3 SQL Validation Rules

1. Must parse as valid SQL
2. Only SELECT statements allowed
3. All tables in allowlist
4. All columns in allowlist
5. No subqueries to non-allowed tables
6. Result limit enforced (max 1000 rows)
7. Query timeout enforced (30 seconds)
