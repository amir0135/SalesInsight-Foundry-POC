# Research: SalesInsight AI Agent

**Feature**: 001-salesinsight-agent  
**Date**: 2026-02-04  
**Status**: Complete

---

## 1. Snowflake Integration

### 1.1 Snowflake Connector Python

**Package**: `snowflake-connector-python`  
**Version**: 3.x (latest stable)

**Key Capabilities**:
- Native Python DB-API 2.0 interface
- Supports parameterized queries (critical for security)
- Connection pooling support
- Schema introspection via `INFORMATION_SCHEMA`

**Connection Pattern**:
```python
import snowflake.connector

conn = snowflake.connector.connect(
    user='service_account',
    password=env_helper.SNOWFLAKE_PASSWORD,
    account='account_identifier',
    warehouse='compute_wh',
    database='sales_db',
    schema='public',
    role='sales_reader'
)
```

**Schema Discovery**:
```sql
-- Get all tables
SELECT TABLE_NAME, TABLE_TYPE 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'PUBLIC';

-- Get columns for a table
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ORDERHISTORYLINE';
```

**Security Best Practices**:
- Use Snowflake Key Pair authentication (preferred over password)
- Store credentials in Azure Key Vault
- Use read-only role for service account
- Enable query tagging for audit

### 1.2 Alternative: Snowflake SQLAlchemy

**Package**: `snowflake-sqlalchemy`

Provides ORM capabilities but may be overkill for read-only analytics queries. Recommend native connector for better control over SQL generation.

---

## 2. Natural Language to SQL (NL2SQL)

### 2.1 GPT-4o for SQL Generation

**Model**: `gpt-4o` (latest from Azure OpenAI)

**Prompt Engineering Strategy**:
1. **Schema Context**: Provide table/column definitions
2. **Business Glossary**: Map business terms to columns
3. **Examples**: Include few-shot examples
4. **Constraints**: Specify output format and safety rules

**Sample System Prompt**:
```
You are a SQL expert. Generate Snowflake SQL queries based on natural language questions about sales data.

AVAILABLE TABLES:
- OrderHistoryLine: Contains sales transactions
  - Columns: OrderID, StyleCode, StyleName, ColorCode, ColorName, VariantCode, Quantity, NetINV, CustomerCode, CustomerName, HoldingCode, HoldingName, Market, Country, Brand, Category, SubCategory, Collection, Season, DeliveryMonth, FiscalYear

BUSINESS GLOSSARY:
- "turnover" = SUM(NetINV)
- "best sold" = ORDER BY Quantity DESC or ORDER BY NetINV DESC
- "FY 25/26" = FiscalYear = '2025-2026' OR (Date >= '2025-07-01' AND Date < '2026-07-01')

RULES:
1. Only use columns from the schema above
2. Always include appropriate GROUP BY for aggregations
3. Limit results to 100 rows unless specified
4. Use parameterized placeholders for user-provided values
5. Never use DELETE, UPDATE, INSERT, DROP, or ALTER

Output JSON: {"sql": "...", "explanation": "...", "parameters": {...}}
```

### 2.2 SQL Validation Strategy

**Multi-Layer Validation**:

1. **Syntax Validation**: Parse SQL with `sqlparse` library
2. **Allowlist Validation**: Check tables/columns against allowlist
3. **Keyword Blocking**: Block DDL and DML statements
4. **Injection Detection**: Check for suspicious patterns

**Allowlist Configuration** (YAML):
```yaml
allowed_tables:
  - OrderHistoryLine

allowed_columns:
  OrderHistoryLine:
    - OrderID
    - StyleCode
    - StyleName
    - ColorCode
    - ColorName
    - VariantCode
    - Quantity
    - NetINV
    - CustomerCode
    - CustomerName
    # ... (all safe columns)

blocked_keywords:
  - DELETE
  - UPDATE
  - INSERT
  - DROP
  - ALTER
  - TRUNCATE
  - EXEC
  - EXECUTE
```

### 2.3 Query Execution Pattern

```python
def execute_safe_query(sql: str, params: dict) -> pd.DataFrame:
    """Execute validated SQL with parameters."""
    # 1. Validate SQL
    if not sql_validator.validate(sql):
        raise SecurityException("SQL validation failed")
    
    # 2. Execute with parameters
    cursor = conn.cursor()
    cursor.execute(sql, params)
    
    # 3. Fetch and convert
    df = cursor.fetch_pandas_all()
    return df
```

---

## 3. Visualization

### 3.1 matplotlib/seaborn for Charts

**Packages**: `matplotlib`, `seaborn`, `pandas`

**Bar Chart Generation**:
```python
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

def generate_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> str:
    """Generate bar chart and return base64 encoded image."""
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df.head(10), x=x_col, y=y_col, palette='viridis')
    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    # Save to buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150)
    buffer.seek(0)
    
    # Encode to base64
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()
    
    return f"data:image/png;base64,{image_base64}"
```

### 3.2 Chart Decision Logic

**When to Generate Charts**:
- Query returns ranked/sorted data (top N)
- Query returns categorical breakdown
- Query returns time series data
- Explicit visualization request in query

**Query Patterns for Charts**:
| Pattern | Chart Type |
|---------|------------|
| "top/best N by X" | Horizontal bar chart |
| "breakdown by category" | Vertical bar chart |
| "compare X and Y" | Grouped bar chart |
| "by month/quarter/year" | Line/Bar chart |

---

## 4. Azure AI Foundry Integration

### 4.1 Agent Service Architecture

**Components**:
- **Agent**: Orchestrates conversation and tool selection
- **Tools**: Callable functions (data query, visualization)
- **Knowledge**: Schema and business context
- **Memory**: Conversation history

**Azure AI Foundry SDK** (Python):
```python
from azure.ai.foundry import AIFoundryClient
from azure.ai.foundry.agents import Agent, Tool

# Initialize client
client = AIFoundryClient(
    endpoint=env_helper.AI_FOUNDRY_ENDPOINT,
    credential=DefaultAzureCredential()
)

# Define tools
query_tool = Tool(
    name="execute_sales_query",
    description="Execute a SQL query against sales data and return results",
    parameters={...},
    function=query_function
)

visualization_tool = Tool(
    name="generate_chart",
    description="Generate a bar chart from query results",
    parameters={...},
    function=chart_function
)

# Create agent
agent = Agent(
    name="SalesInsightAgent",
    instructions=system_prompt,
    tools=[query_tool, visualization_tool],
    model="gpt-4o"
)
```

### 4.2 Tool Definitions

**QueryTool**:
- Input: Natural language question
- Process: NL2SQL → Validate → Execute
- Output: DataFrame as JSON + metadata

**VisualizationTool**:
- Input: Query results, chart type
- Process: Generate chart → Encode
- Output: Base64 image string

**SchemaTool**:
- Input: Table name (optional)
- Process: Fetch from cache/Snowflake
- Output: Schema definition JSON

### 4.3 Orchestration Strategy

Extend existing `ORCHESTRATION_STRATEGY` pattern:

```python
# New strategy: ai_foundry
class AIFoundryOrchestrator(OrchestratorBase):
    def __init__(self, env_helper):
        self.agent = create_foundry_agent(env_helper)
    
    async def orchestrate(self, question: str, chat_history: list):
        response = await self.agent.run(
            message=question,
            history=chat_history
        )
        return self.format_response(response)
```

---

## 5. Frontend Integration

### 5.1 Image Rendering in Chat

Extend existing ChatMessage component to handle image responses:

```typescript
// In ChatMessage component
{message.chart && (
  <img 
    src={message.chart} 
    alt="Data visualization"
    className={styles.chartImage}
  />
)}
```

### 5.2 Response Structure

```json
{
  "answer": "The top 5 best sold styles are...",
  "chart": "data:image/png;base64,iVBORw0KGgo...",
  "sources": [],
  "metadata": {
    "query_type": "sales_analytics",
    "execution_time_ms": 1250,
    "rows_returned": 5
  }
}
```

---

## 6. Infrastructure Requirements

### 6.1 New Azure Resources

| Resource | Purpose | SKU |
|----------|---------|-----|
| Azure AI Foundry Project | Agent hosting | Standard |
| Azure Key Vault Secret | Snowflake credentials | Standard |
| Application Insights | Agent monitoring | (existing) |

### 6.2 Environment Variables

New variables for `EnvHelper`:
```python
# Snowflake
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "SALES_READER")
# Password from Key Vault via SecretHelper

# AI Foundry
AI_FOUNDRY_ENDPOINT = os.getenv("AI_FOUNDRY_ENDPOINT")
AI_FOUNDRY_PROJECT = os.getenv("AI_FOUNDRY_PROJECT")
```

---

## 7. Security Considerations

### 7.1 SQL Injection Prevention

1. **Parameterized Queries**: Always use `%s` placeholders
2. **Allowlist Validation**: Only permitted tables/columns
3. **Query Logging**: Full audit trail
4. **Rate Limiting**: Prevent abuse

### 7.2 Credential Management

1. Store Snowflake password in Azure Key Vault
2. Use Managed Identity for Azure resources
3. Rotate credentials regularly
4. Minimal privilege for service account

### 7.3 Data Access Control

1. Read-only Snowflake role
2. No PII columns in allowlist (if applicable)
3. Result set size limits
4. Query timeout enforcement

---

## 8. Performance Optimization

### 8.1 Query Optimization

- Use Snowflake result caching
- Optimize common query patterns
- Index usage validation
- Query timeout: 30 seconds

### 8.2 Response Caching

- Cache schema metadata (5 min TTL)
- Cache common query results (configurable)
- Cache chart templates

### 8.3 Connection Pooling

- Use connection pool for Snowflake
- Configure pool size based on concurrency needs
- Implement connection health checks

---

## 9. Testing Strategy

### 9.1 Unit Tests

- SQL generator with mock GPT-4o responses
- SQL validator with test cases
- Chart generator with sample data
- Tool functions with mocked dependencies

### 9.2 Integration Tests

- Snowflake connection (with test database)
- End-to-end query flow
- Agent orchestration

### 9.3 Security Tests

- SQL injection attempts
- Blocked keyword detection
- Allowlist enforcement
- Authentication validation

---

## 10. References

- [Snowflake Python Connector Docs](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector)
- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [GPT-4o Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- [matplotlib Documentation](https://matplotlib.org/stable/contents.html)
- [Existing Trackman Integration Pattern](../../../code/backend/batch/utilities/) (internal reference)
