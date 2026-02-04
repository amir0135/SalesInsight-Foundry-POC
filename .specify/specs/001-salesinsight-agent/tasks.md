# Implementation Tasks: SalesInsight AI Agent

**Feature**: 001-salesinsight-agent  
**Date**: 2026-02-04  
**Status**: Ready for Implementation

---

## Phase 0: Prerequisites & Setup

### Phase 0.1: Environment Setup

- [ ] **Task 0.1.1**: Add new Python dependencies
  - File: `pyproject.toml`
  - Add: snowflake-connector-python ^3.6.0, matplotlib ^3.8.0, seaborn ^0.13.0, sqlparse ^0.5.0
  - Run: `poetry lock && poetry install`
  - **Verify**: `poetry show snowflake-connector-python`

- [ ] **Task 0.1.2**: Create test infrastructure [P]
  - File: `code/tests/conftest.py`
  - Add Snowflake mock fixtures
  - Add sample DataFrame fixtures for visualization tests
  - Create mock GPT response fixtures
  - **Test**: Run existing test suite to verify no regressions

- [ ] **Task 0.1.3**: Create configuration files
  - File: `code/backend/batch/utilities/nl2sql/config/allowlist_config.yaml`
  - File: `code/backend/batch/utilities/nl2sql/config/business_glossary.yaml`
  - Define initial OrderHistoryLine allowlist
  - Define business term mappings (turnover → SUM(NetINV))
  - **Test**: YAML schema validation

**Checkpoint 0.1**: ✅ Dependencies installed, configuration files created

---

## User Story 1: Query Best Sold Styles (P1)

### Phase 1.1: Snowflake Data Source

- [ ] **Task 1.1.1**: Create base data source interface
  - File: `code/backend/batch/utilities/data_sources/base_data_source.py`
  - Create abstract `BaseDataSource` class with `connect()`, `execute()`, `get_schema()` methods
  - Add type hints and docstrings
  - **Test**: `code/tests/test_base_datasource.py`

- [ ] **Task 1.1.2**: Implement Snowflake connector
  - File: `code/backend/batch/utilities/data_sources/snowflake_data_source.py`
  - Implement `SnowflakeDataSource` extending base class
  - Add connection pooling with `snowflake-connector-python`
  - Use parameterized queries
  - **Test**: `code/tests/test_snowflake_datasource.py`

- [ ] **Task 1.1.3**: Add Snowflake environment configuration [P]
  - File: `code/backend/batch/utilities/helpers/env_helper.py`
  - Add Snowflake-related environment variables
  - Integrate with `SecretHelper` for credentials from Key Vault
  - **Test**: Extend existing env_helper tests

- [ ] **Task 1.1.4**: Implement schema discovery
  - File: `code/backend/batch/utilities/data_sources/schema_discovery.py`
  - Query `INFORMATION_SCHEMA` for tables and columns
  - Cache schema with configurable TTL
  - Include sample values for context
  - **Test**: `code/tests/test_schema_discovery.py`

**Checkpoint 1.1**: ✅ Snowflake connection working, schema discovery tested

### Phase 1.2: NL2SQL Engine

- [ ] **Task 1.2.1**: Create SQL generator
  - File: `code/backend/batch/utilities/nl2sql/sql_generator.py`
  - Implement `SQLGenerator` class using Azure OpenAI GPT-4o
  - Include schema context and business glossary in prompt
  - Return structured response with SQL, parameters, explanation
  - **Test**: `code/tests/test_sql_generator.py` (with mocked GPT responses)

- [ ] **Task 1.2.2**: Create allowlist manager
  - File: `code/backend/batch/utilities/nl2sql/allowlist_manager.py`
  - Load allowlist from YAML configuration
  - Provide validation methods for tables and columns
  - Support blocked keyword list
  - **Test**: `code/tests/test_allowlist_manager.py`

- [ ] **Task 1.2.3**: Create SQL validator
  - File: `code/backend/batch/utilities/nl2sql/sql_validator.py`
  - Parse SQL with `sqlparse`
  - Validate against allowlist
  - Check for blocked keywords (DELETE, UPDATE, DROP, etc.)
  - Detect SQL injection patterns
  - **Test**: `code/tests/test_sql_validator.py` (security test cases)

- [ ] **Task 1.2.4**: Create query executor
  - File: `code/backend/batch/utilities/nl2sql/query_executor.py`
  - Execute validated SQL with parameters
  - Convert results to pandas DataFrame
  - Enforce result limits and timeouts
  - Log queries for audit
  - **Test**: `code/tests/test_query_executor.py`

**Checkpoint 1.2**: ✅ NL2SQL pipeline working end-to-end with security

---

## User Story 7: Bar Chart Visualization (P1)

### Phase 2.1: Chart Generation

- [ ] **Task 2.1.1**: Create chart generator base [P]
  - File: `code/backend/batch/utilities/visualization/chart_generator.py`
  - Abstract `ChartGenerator` base class
  - Define `generate()` method signature
  - Include chart configuration dataclass
  - **Test**: `code/tests/test_chart_generator.py`

- [ ] **Task 2.1.2**: Implement bar chart generator
  - File: `code/backend/batch/utilities/visualization/bar_chart.py`
  - Implement `BarChartGenerator` using matplotlib/seaborn
  - Support vertical, horizontal, and grouped bar charts
  - Configure colors, labels, titles
  - **Test**: `code/tests/test_bar_chart.py`

- [ ] **Task 2.1.3**: Create chart embedder
  - File: `code/backend/batch/utilities/visualization/chart_embedder.py`
  - Convert matplotlib figures to base64 PNG
  - Optimize image size (max 500KB)
  - Support data URI format for embedding
  - **Test**: `code/tests/test_chart_embedder.py`

- [ ] **Task 2.1.4**: Add visualization decision logic
  - File: `code/backend/batch/utilities/visualization/__init__.py`
  - Analyze query results to decide if chart is appropriate
  - Map query types to chart types
  - Return chart configuration or None
  - **Test**: `code/tests/test_visualization_decision.py`

**Checkpoint 2.1**: ✅ Bar charts generating correctly from DataFrame input

---

## User Story 2 & 3: Market/Collection Queries (P1)

### Phase 3.1: Business Logic Enhancement

- [ ] **Task 3.1.1**: Create business glossary configuration
  - File: `code/backend/batch/utilities/nl2sql/business_glossary.yaml`
  - Map business terms to SQL (turnover → SUM(NetINV))
  - Define fiscal year date ranges
  - Include entity synonyms
  - **Test**: Validate YAML schema

- [ ] **Task 3.1.2**: Enhance SQL generator with glossary
  - File: `code/backend/batch/utilities/nl2sql/sql_generator.py`
  - Load glossary into prompt context
  - Handle fiscal year calculations
  - Support market and brand filtering
  - **Test**: `code/tests/test_sql_generator.py` (extend with market/brand cases)

- [ ] **Task 3.1.3**: Add entity disambiguation
  - File: `code/backend/batch/utilities/nl2sql/entity_resolver.py`
  - Match partial entity names to database values
  - Suggest alternatives for unknown entities
  - Cache entity lists for performance
  - **Test**: `code/tests/test_entity_resolver.py`

**Checkpoint 3.1**: ✅ Market and collection queries working with proper filtering

---

## User Story Integration: Azure AI Foundry (P1)

### Phase 4.1: Agent Integration

- [ ] **Task 4.1.1**: Create query tool
  - File: `code/backend/batch/utilities/agents/tools/query_tool.py`
  - Define tool schema for AI Foundry
  - Implement tool function wrapping NL2SQL pipeline
  - Handle errors gracefully
  - **Test**: `code/tests/test_query_tool.py`

- [ ] **Task 4.1.2**: Create visualization tool [P]
  - File: `code/backend/batch/utilities/agents/tools/visualization_tool.py`
  - Define tool schema for chart generation
  - Accept DataFrame and configuration
  - Return base64 image
  - **Test**: `code/tests/test_visualization_tool.py`

- [ ] **Task 4.1.3**: Create schema tool
  - File: `code/backend/batch/utilities/agents/tools/schema_tool.py`
  - Define tool for schema exploration
  - Return table/column information
  - Support filtering by table name
  - **Test**: `code/tests/test_schema_tool.py`

- [ ] **Task 4.1.4**: Implement Foundry agent
  - File: `code/backend/batch/utilities/agents/foundry_agent.py`
  - Initialize AI Foundry client
  - Register tools with agent
  - Configure system prompt with context
  - Handle conversation history
  - **Test**: `code/tests/test_foundry_agent.py`

- [ ] **Task 4.1.5**: Create orchestration strategy
  - File: `code/backend/batch/utilities/agents/orchestration_strategy.py`
  - Extend `OrchestratorBase` pattern
  - Integrate with existing strategy selection
  - Add `ai_foundry` as strategy option
  - **Test**: `code/tests/test_orchestration_strategy.py`

**Checkpoint 4.1**: ✅ AI Foundry agent orchestrating tools correctly

---

## User Story UI: Chat Interface (P1)

### Phase 5.1: API Endpoint

- [ ] **Task 5.1.1**: Create sales query API endpoint
  - File: `code/backend/api/routes/sales_query.py`
  - Implement `POST /api/sales/query`
  - Handle request validation
  - Integrate with Foundry agent
  - Return structured response
  - **Test**: `code/tests/test_sales_query_api.py`

- [ ] **Task 5.1.2**: Register route in Flask app
  - File: `code/create_app.py`
  - Import and register sales_query blueprint
  - Add CORS configuration if needed
  - **Test**: Integration test

- [ ] **Task 5.1.3**: Implement error handling middleware
  - File: `code/backend/api/middleware/error_handler.py`
  - Create centralized error handling for sales API
  - Define user-friendly error messages for common failures
  - Log errors to Application Insights
  - Return structured error responses (see contracts/api-spec.json)
  - **Test**: `code/tests/test_error_handler.py`
  - **Constitution**: Principle IV - Comprehensive error handling

### Phase 5.2: Frontend Integration

- [ ] **Task 5.2.1**: Extend ChatMessage for images
  - File: `code/frontend/src/components/ChatMessage/ChatMessage.tsx`
  - Add image rendering for chart responses
  - Style chart images appropriately
  - Handle loading states
  - **Test**: `code/frontend/src/components/ChatMessage/ChatMessage.test.tsx`

- [ ] **Task 5.2.2**: Update API client
  - File: `code/frontend/src/api/salesApi.ts`
  - Add sales query API client function
  - Handle response parsing with chart data
  - **Test**: `code/frontend/src/api/salesApi.test.ts`

**Checkpoint 5.1**: ✅ End-to-end query flow working in UI

---

## User Story 4: Detailed Customer Lists (P2)

### Phase 6.1: List Query Support

- [ ] **Task 6.1.1**: Enhance SQL generator for detail queries
  - File: `code/backend/batch/utilities/nl2sql/sql_generator.py`
  - Support multi-column SELECT for detailed lists
  - Handle customer/holding name matching
  - Add pagination logic
  - **Test**: Extend existing tests

- [ ] **Task 6.1.2**: Add table formatting for responses
  - File: `code/backend/batch/utilities/response/table_formatter.py`
  - Format DataFrame as markdown table
  - Truncate for large result sets
  - Suggest export for full data
  - **Test**: `code/tests/test_table_formatter.py`

**Checkpoint 6.1**: ✅ Detailed list queries returning formatted tables

---

## User Story 5 & 6: Category and FY Analysis (P2)

### Phase 7.1: Advanced Query Support

- [ ] **Task 7.1.1**: Add category hierarchy support
  - File: `code/backend/batch/utilities/nl2sql/sql_generator.py`
  - Handle category and subcategory filtering
  - Support category aggregation
  - **Test**: Extend existing tests

- [ ] **Task 7.1.2**: Add comparison queries
  - File: `code/backend/batch/utilities/nl2sql/sql_generator.py`
  - Support "compare X vs Y" pattern
  - Generate grouped bar chart config
  - Calculate percentage changes
  - **Test**: Extend existing tests

**Checkpoint 7.1**: ✅ Category and comparison queries working

---

## User Story 8: Delivery Month Analysis (P3)

### Phase 8.1: Time Series Support

- [ ] **Task 8.1.1**: Add temporal grouping
  - File: `code/backend/batch/utilities/nl2sql/sql_generator.py`
  - Handle month/quarter/year grouping
  - Support date range filtering
  - **Test**: Extend existing tests

**Checkpoint 8.1**: ✅ Temporal queries working

---

## Deployment & Infrastructure

### Phase 9.1: Azure Infrastructure

- [ ] **Task 9.1.1**: Create AI Foundry Bicep module
  - File: `infra/modules/ai-foundry.bicep`
  - Define AI Foundry project resource
  - Configure agent service
  - Set up managed identity
  - **Test**: `azd provision --preview`

- [ ] **Task 9.1.2**: Add Snowflake secrets to Key Vault
  - File: `infra/modules/keyvault.bicep` (extend)
  - Add Snowflake password secret
  - Configure access policies
  - **Test**: Verify secret access

- [ ] **Task 9.1.3**: Update main Bicep template
  - File: `infra/main.bicep`
  - Add AI Foundry module reference
  - Add new environment variables
  - Update dependencies
  - **Test**: Full deployment test

- [ ] **Task 9.1.4**: Update azure.yaml for new service
  - File: `azure.yaml`
  - Add any new service configurations
  - Update environment variables
  - **Test**: `azd up` validation

### Phase 9.2: Testing & Validation

- [ ] **Task 9.2.1**: Performance testing
  - File: `code/tests/performance/test_query_performance.py`
  - Validate NFR-001: < 10 second response time
  - Test with 10 concurrent users (NFR-002)
  - Measure SQL generation latency
  - Measure Snowflake query latency
  - **Tool**: pytest with pytest-benchmark or locust
  - **Test**: Performance baseline established

- [ ] **Task 9.2.2**: Security testing
  - File: `code/tests/security/test_sql_injection.py`
  - SQL injection attack vectors
  - Allowlist bypass attempts
  - Credential exposure tests
  - **Test**: All security tests pass

### Phase 9.3: Documentation

- [ ] **Task 9.3.1**: Create quickstart guide
  - File: `.specify/specs/001-salesinsight-agent/quickstart.md`
  - Developer setup instructions
  - Local testing guide
  - Sample queries

- [ ] **Task 9.3.2**: Update main README
  - File: `README.md`
  - Add sales insight feature documentation
  - Include API usage examples
  - Document environment variables

- [ ] **Task 9.3.3**: Create user guide
  - File: `docs/sales_insight_guide.md`
  - Query examples for sales users
  - Supported question types
  - Troubleshooting tips

**Checkpoint 9.3**: ✅ One-click deployment working, documentation complete

---

## Dependencies (pyproject.toml additions)

```toml
[tool.poetry.dependencies]
snowflake-connector-python = "^3.6.0"
matplotlib = "^3.8.0"
seaborn = "^0.13.0"
sqlparse = "^0.5.0"
azure-ai-foundry = "^1.0.0"  # Or latest SDK name
pyyaml = "^6.0"
```

---

## Test Coverage Requirements

| Component | Target Coverage | Test Type |
|-----------|-----------------|-----------|
| Snowflake Data Source | 90% | Unit + Integration |
| NL2SQL Engine | 95% | Unit + Security |
| Visualization | 85% | Unit |
| Agent Integration | 80% | Unit + Integration |
| API Endpoints | 90% | Unit + Functional |
| Frontend Components | 80% | Unit |

---

## Task Legend

- `[P]` = Can be parallelized with previous task
- ✅ = Checkpoint - validate before proceeding
- File paths are relative to repository root
- All tasks include corresponding test files
