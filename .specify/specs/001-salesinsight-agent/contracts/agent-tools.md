# AI Foundry Agent Tool Definitions

**Feature**: 001-salesinsight-agent  
**Date**: 2026-02-04

---

## Overview

This document defines the tools available to the SalesInsight AI Foundry Agent. The agent orchestrates these tools to answer natural language questions about sales data.

---

## Tool 1: execute_sales_query

**Purpose**: Convert natural language to SQL and execute against Snowflake

### Schema

```json
{
  "name": "execute_sales_query",
  "description": "Converts a natural language question about sales data into SQL, validates it for security, executes against the Snowflake database, and returns the results as structured data.",
  "parameters": {
    "type": "object",
    "properties": {
      "question": {
        "type": "string",
        "description": "The natural language question about sales data to answer"
      },
      "filters": {
        "type": "object",
        "description": "Optional explicit filters to apply",
        "properties": {
          "market": {
            "type": "string",
            "description": "Filter by market/country"
          },
          "brand": {
            "type": "string",
            "description": "Filter by brand"
          },
          "collection": {
            "type": "string",
            "description": "Filter by collection code"
          },
          "fiscal_year": {
            "type": "string",
            "description": "Filter by fiscal year (e.g., 'FY 25/26')"
          },
          "category": {
            "type": "string",
            "description": "Filter by product category"
          }
        }
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of rows to return",
        "default": 100
      }
    },
    "required": ["question"]
  }
}
```

### Example Invocation

```json
{
  "name": "execute_sales_query",
  "arguments": {
    "question": "What are the best sold styles?",
    "filters": {
      "market": "France",
      "fiscal_year": "FY 25/26"
    },
    "limit": 10
  }
}
```

### Response Format

```json
{
  "success": true,
  "data": [
    {
      "StyleCode": "STYLE-001",
      "StyleName": "Classic Dress",
      "TotalQuantity": 2450,
      "TotalTurnover": 125000.00
    }
  ],
  "metadata": {
    "sql_executed": "SELECT StyleCode, StyleName, SUM(Quantity) AS TotalQuantity...",
    "row_count": 10,
    "execution_time_ms": 850
  }
}
```

---

## Tool 2: generate_visualization

**Purpose**: Generate bar charts from query results

### Schema

```json
{
  "name": "generate_visualization",
  "description": "Generates a bar chart visualization from structured data. Use this tool after execute_sales_query when the data would benefit from visual representation.",
  "parameters": {
    "type": "object",
    "properties": {
      "data": {
        "type": "array",
        "description": "Array of data objects to visualize",
        "items": {
          "type": "object"
        }
      },
      "x_column": {
        "type": "string",
        "description": "Column name for X-axis (categories)"
      },
      "y_column": {
        "type": "string",
        "description": "Column name for Y-axis (values)"
      },
      "chart_type": {
        "type": "string",
        "enum": ["bar", "horizontal_bar", "grouped_bar"],
        "description": "Type of bar chart to generate",
        "default": "bar"
      },
      "title": {
        "type": "string",
        "description": "Chart title"
      },
      "x_label": {
        "type": "string",
        "description": "X-axis label"
      },
      "y_label": {
        "type": "string",
        "description": "Y-axis label"
      },
      "group_column": {
        "type": "string",
        "description": "Column for grouping in grouped_bar charts"
      }
    },
    "required": ["data", "x_column", "y_column", "title"]
  }
}
```

### Example Invocation

```json
{
  "name": "generate_visualization",
  "arguments": {
    "data": [
      {"StyleName": "Classic Dress", "TotalQuantity": 2450},
      {"StyleName": "Summer Blouse", "TotalQuantity": 1890},
      {"StyleName": "Evening Gown", "TotalQuantity": 1650}
    ],
    "x_column": "StyleName",
    "y_column": "TotalQuantity",
    "chart_type": "horizontal_bar",
    "title": "Top Selling Styles in France",
    "y_label": "Units Sold"
  }
}
```

### Response Format

```json
{
  "success": true,
  "chart": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA...",
  "metadata": {
    "chart_type": "horizontal_bar",
    "data_points": 3,
    "image_size_bytes": 45678
  }
}
```

---

## Tool 3: get_schema_info

**Purpose**: Retrieve available schema information for context

### Schema

```json
{
  "name": "get_schema_info",
  "description": "Retrieves schema information about available tables and columns in the sales database. Use this tool when you need to understand what data is available or to clarify column names.",
  "parameters": {
    "type": "object",
    "properties": {
      "table_name": {
        "type": "string",
        "description": "Specific table to get schema for (optional, returns all if not specified)"
      },
      "include_sample_values": {
        "type": "boolean",
        "description": "Whether to include sample values for columns",
        "default": false
      }
    },
    "required": []
  }
}
```

### Example Invocation

```json
{
  "name": "get_schema_info",
  "arguments": {
    "table_name": "OrderHistoryLine",
    "include_sample_values": true
  }
}
```

### Response Format

```json
{
  "success": true,
  "tables": [
    {
      "name": "OrderHistoryLine",
      "description": "Sales transaction line items",
      "columns": [
        {
          "name": "StyleCode",
          "type": "VARCHAR",
          "description": "Product style code",
          "sample_values": ["STYLE-001", "STYLE-042", "STYLE-103"]
        },
        {
          "name": "Market",
          "type": "VARCHAR",
          "description": "Market/region code",
          "sample_values": ["France", "Germany", "Italy", "UK"]
        }
      ],
      "row_count": 50000
    }
  ]
}
```

---

## Tool 4: resolve_entity

**Purpose**: Resolve ambiguous entity names

### Schema

```json
{
  "name": "resolve_entity",
  "description": "Resolves ambiguous entity names (customers, brands, markets, etc.) to their exact database values. Use when the user provides a partial name or unclear reference.",
  "parameters": {
    "type": "object",
    "properties": {
      "entity_type": {
        "type": "string",
        "enum": ["customer", "holding", "brand", "market", "category", "collection", "style"],
        "description": "Type of entity to resolve"
      },
      "search_term": {
        "type": "string",
        "description": "Partial name or search term provided by user"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of matches to return",
        "default": 5
      }
    },
    "required": ["entity_type", "search_term"]
  }
}
```

### Example Invocation

```json
{
  "name": "resolve_entity",
  "arguments": {
    "entity_type": "customer",
    "search_term": "Galeries",
    "limit": 3
  }
}
```

### Response Format

```json
{
  "success": true,
  "matches": [
    {
      "code": "CUST-001",
      "name": "Galeries Lafayette Paris",
      "confidence": 0.95
    },
    {
      "code": "CUST-042",
      "name": "Galeries Lafayette Lyon",
      "confidence": 0.90
    }
  ],
  "exact_match": false
}
```

---

## Agent System Prompt

```
You are a sales analytics assistant that helps sales teams analyze their sell-in data. 
You have access to the OrderHistoryLine table containing sales transactions.

AVAILABLE TOOLS:
1. execute_sales_query - Convert questions to SQL and get results
2. generate_visualization - Create bar charts from data
3. get_schema_info - Get table/column information
4. resolve_entity - Clarify ambiguous names

WORKFLOW:
1. For analytical questions, use execute_sales_query first
2. If data is suitable for visualization (ranked, categorical), use generate_visualization
3. If entity names are ambiguous, use resolve_entity to clarify
4. If unsure about available data, use get_schema_info

RESPONSE GUIDELINES:
- Provide clear, concise summaries of the data
- Use bullet points or numbered lists for rankings
- Include relevant numbers with proper formatting (currency, percentages)
- When generating charts, choose appropriate chart types
- If a query cannot be answered, explain why and suggest alternatives

BUSINESS CONTEXT:
- "Turnover" means SUM(NetINV)
- "Best sold" means highest quantity or turnover
- Fiscal year FY 25/26 runs from July 2025 to June 2026
- Markets include France, Germany, Italy, UK, Spain, etc.
```

---

## Tool Orchestration Patterns

### Pattern 1: Simple Aggregation Query

```
User: "What are the best sold styles?"

1. Agent calls execute_sales_query(question="What are the best sold styles?")
2. Receives data with StyleCode, StyleName, TotalQuantity, TotalTurnover
3. Agent calls generate_visualization(data=..., chart_type="horizontal_bar")
4. Agent composes response with text summary + chart
```

### Pattern 2: Filtered Analysis

```
User: "What is the turnover in France for Brand X this year?"

1. Agent calls execute_sales_query(question="...", filters={market: "France", brand: "Brand X"})
2. Receives aggregated turnover value
3. Agent composes text-only response (single value, no chart needed)
```

### Pattern 3: Ambiguous Entity

```
User: "Show sales to Galeries"

1. Agent calls resolve_entity(entity_type="customer", search_term="Galeries")
2. Receives multiple matches
3. Agent asks user to clarify: "Did you mean Galeries Lafayette Paris or Galeries Lafayette Lyon?"
4. User clarifies
5. Agent calls execute_sales_query with resolved customer
```

### Pattern 4: Comparison Query

```
User: "Compare sales in Germany vs Italy"

1. Agent calls execute_sales_query(question="Compare sales in Germany vs Italy")
2. Receives data grouped by market
3. Agent calls generate_visualization(chart_type="grouped_bar", group_column="Market")
4. Agent composes response with comparison text + grouped chart
```
