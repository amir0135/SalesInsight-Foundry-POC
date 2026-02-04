# Implementation Plan: SalesInsight AI Agent

**Branch**: `001-salesinsight-agent` | **Date**: 2026-02-04 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/001-salesinsight-agent/spec.md`

## Summary

Build an AI-powered sales analytics agent that enables natural language querying of Snowflake sales data, generating both textual summaries and bar chart visualizations. The solution leverages Azure AI Foundry for agent orchestration, GPT-4o for NL2SQL conversion, and integrates with the existing chat-with-your-data architecture.

---

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: 
- Flask (existing backend framework)
- React (existing frontend)
- Azure AI Foundry SDK
- Azure OpenAI (GPT-4o)
- snowflake-connector-python
- matplotlib, seaborn, pandas
- Semantic Kernel / LangChain (existing orchestrators)

**Storage**: 
- Snowflake (primary sales data)
- Azure Blob Storage (config, document storage)
- PostgreSQL/CosmosDB (conversation history - existing)

**Testing**: pytest (existing framework with markers)  
**Target Platform**: Azure App Service, Azure Functions  
**Performance Goals**: < 10 second response time, 10 concurrent users  
**Constraints**: SQL injection prevention, table/column allowlists, < 200ms SQL validation  
**Scale/Scope**: 50K+ rows OrderHistoryLine, single data source POC

---

## Constitution Check

*GATE: Verified against constitution principles*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. User Experience First | ✅ | Natural language queries, visual responses |
| II. Data Integrity & Security | ✅ | Parameterized queries, allowlists, validation |
| III. Azure-First Architecture | ✅ | AI Foundry, Azure OpenAI, Bicep deployment |
| IV. Code Quality Standards | ✅ | Python typing, modular design, documentation |
| V. Testing Requirements | ✅ | Unit, integration, e2e tests defined |
| VI. Extensibility | ✅ | Data source agnostic design, visualization extensible |

---

## Project Structure

### Documentation (this feature)

```text
.specify/specs/001-salesinsight-agent/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Technology research
├── data-model.md        # Schema and entity definitions
├── quickstart.md        # Developer getting started guide
├── contracts/           # API contracts
│   ├── api-spec.json    # OpenAPI spec for new endpoints
│   └── agent-tools.md   # AI Foundry tool definitions
└── tasks.md             # Implementation task breakdown
```

### Source Code (repository root)

```text
code/
├── app.py                           # Flask entry point (existing)
├── create_app.py                    # Route registration (extend)
├── backend/
│   ├── batch/
│   │   ├── utilities/
│   │   │   ├── data_sources/        # NEW: Data source connectors
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_data_source.py
│   │   │   │   ├── snowflake_data_source.py
│   │   │   │   └── schema_discovery.py
│   │   │   ├── nl2sql/              # NEW: NL2SQL engine
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sql_generator.py
│   │   │   │   ├── sql_validator.py
│   │   │   │   ├── query_executor.py
│   │   │   │   └── allowlist_manager.py
│   │   │   ├── visualization/       # NEW: Chart generation
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chart_generator.py
│   │   │   │   ├── bar_chart.py
│   │   │   │   └── chart_embedder.py
│   │   │   ├── agents/              # NEW: AI Foundry integration
│   │   │   │   ├── __init__.py
│   │   │   │   ├── foundry_agent.py
│   │   │   │   ├── tools/
│   │   │   │   │   ├── query_tool.py
│   │   │   │   │   ├── visualization_tool.py
│   │   │   │   │   └── schema_tool.py
│   │   │   │   └── orchestration_strategy.py
│   │   │   ├── helpers/
│   │   │   │   └── env_helper.py    # Extend for Snowflake config
│   │   │   └── orchestrator/
│   │   │       └── strategies/      # Extend existing strategies
│   │   └── function_app.py          # Azure Functions (extend)
│   └── api/
│       └── routes/
│           └── sales_query.py       # NEW: Sales query API endpoint
├── frontend/
│   └── src/
│       └── components/
│           └── ChatMessage/         # Extend for chart rendering
└── tests/
    ├── test_snowflake_datasource.py # NEW
    ├── test_nl2sql.py               # NEW
    ├── test_visualization.py        # NEW
    ├── test_foundry_agent.py        # NEW
    └── utilities/
        └── test_sales_queries.py    # NEW: Integration tests
```

### Infrastructure

```text
infra/
├── main.bicep                       # Extend for new resources
├── modules/
│   ├── ai-foundry.bicep             # NEW: AI Foundry resources
│   ├── snowflake-secret.bicep       # NEW: Key Vault for Snowflake creds
│   └── ... (existing modules)
└── main.parameters.json             # Extend with new parameters
```

---

## Implementation Phases

### Phase 0: Research & Setup (1-2 days)

**Objective**: Validate technology choices and set up development environment

1. **Snowflake Connector Research**
   - Validate snowflake-connector-python compatibility
   - Test connection with sample credentials
   - Document schema discovery approach

2. **Azure AI Foundry Research**
   - Review Agent Service capabilities
   - Define tool registration pattern
   - Validate GPT-4o integration path

3. **Environment Setup**
   - Add new dependencies to pyproject.toml
   - Configure Snowflake environment variables
   - Set up local testing infrastructure

### Phase 1: Core Infrastructure (3-4 days)

**Objective**: Build foundational components

1. **Snowflake Data Source**
   - Implement `SnowflakeDataSource` class
   - Implement schema discovery
   - Add connection pooling
   - Write unit tests

2. **NL2SQL Engine**
   - Implement `SQLGenerator` with GPT-4o
   - Implement `SQLValidator` with allowlists
   - Implement `QueryExecutor`
   - Write validation tests

3. **Security Layer**
   - Implement `AllowlistManager`
   - Add parameterized query support
   - Implement query logging

### Phase 2: Visualization (2 days)

**Objective**: Build chart generation pipeline

1. **Chart Generator**
   - Implement base `ChartGenerator` class
   - Implement `BarChartGenerator`
   - Implement base64 embedding

2. **Chart Integration**
   - Add decision logic for when to visualize
   - Integrate with response pipeline
   - Write visualization tests

### Phase 3: Agent Integration (2-3 days)

**Objective**: Integrate with Azure AI Foundry

1. **Tool Definitions**
   - Define `QueryTool` for data retrieval
   - Define `VisualizationTool` for charts
   - Define `SchemaTool` for metadata

2. **Agent Service**
   - Implement `FoundryAgent` class
   - Register tools with agent service
   - Implement orchestration strategy

3. **Conversation Flow**
   - Integrate with existing conversation handlers
   - Add context management
   - Test end-to-end flows

### Phase 4: UI Integration (1-2 days)

**Objective**: Enable chat interface for sales queries

1. **API Endpoint**
   - Implement `/api/sales/query` endpoint
   - Add request/response models
   - Integrate with authentication

2. **Frontend Updates**
   - Extend ChatMessage for image rendering
   - Add loading states
   - Test UI interactions

### Phase 5: Deployment & Testing (2 days)

**Objective**: Prepare for production deployment

1. **Infrastructure**
   - Create AI Foundry Bicep module
   - Add Key Vault secrets for Snowflake
   - Update deployment scripts

2. **Testing**
   - Run full test suite
   - Perform security review
   - Validate one-click deployment

3. **Documentation**
   - Update README
   - Create user guide
   - Document API contracts

---

## Dependencies & Risks

### Dependencies

| Dependency | Impact | Mitigation |
|------------|--------|------------|
| Snowflake access | Blocks Phase 1 | Get credentials early |
| Azure AI Foundry access | Blocks Phase 3 | Validate subscription capabilities |
| Sample data CSV | Blocks testing | Use provided 50K row sample |
| GPT-4o deployment | Blocks NL2SQL | Use existing Azure OpenAI resource |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| NL2SQL accuracy < 90% | Medium | High | Extensive prompt engineering, fallback queries |
| Snowflake performance | Low | Medium | Query optimization, result limits |
| AI Foundry limitations | Medium | Medium | Fallback to direct orchestration |
| Chart rendering in UI | Low | Low | Base64 standard, fallback to text |

---

## Success Criteria

1. **Functional**: All P1 user stories pass acceptance tests
2. **Performance**: 95% of queries complete in < 10 seconds
3. **Security**: Zero SQL injection vulnerabilities
4. **Accuracy**: > 90% correct SQL generation for test queries
5. **Deployment**: One-click Azure deployment works end-to-end

---

## Estimated Timeline

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 0: Research | 2 days | Day 1 | Day 2 |
| Phase 1: Core Infrastructure | 4 days | Day 3 | Day 6 |
| Phase 2: Visualization | 2 days | Day 7 | Day 8 |
| Phase 3: Agent Integration | 3 days | Day 9 | Day 11 |
| Phase 4: UI Integration | 2 days | Day 12 | Day 13 |
| Phase 5: Deployment | 2 days | Day 14 | Day 15 |

**Total Estimated Duration**: 15 working days (3 weeks)
