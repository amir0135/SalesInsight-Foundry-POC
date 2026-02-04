# SalesInsight AI Agent - Project Constitution

## Project Vision

Build an AI-powered sales analytics agent that enables sales teams to query complex business data using natural language, providing both textual summaries and visual bar charts to answer key business questions about sell-in data.

## Core Principles

### I. User Experience First

- **Natural Language Priority**: The agent must understand and respond to natural language queries without requiring technical knowledge from sales users
- **Response Quality**: Answers must be accurate, concise, and actionable for sales preparation
- **Visual Insights**: Provide bar charts alongside text summaries when data visualization adds value
- **Response Time**: Queries should complete within acceptable time limits (< 10 seconds for typical queries)

### II. Data Integrity & Security (NON-NEGOTIABLE)

- **SQL Injection Prevention**: All SQL generation MUST use parameterized queries
- **Access Control**: Implement table/column allowlists to prevent unauthorized data access
- **Data Validation**: Validate all generated SQL before execution
- **Audit Logging**: Log all queries and data access for compliance

### III. Azure-First Architecture

- **Azure AI Foundry**: Use Azure AI Foundry for agent orchestration and tool management
- **Azure OpenAI**: Leverage GPT-4o for NL2SQL conversion and response generation
- **Azure AI Search**: Maintain compatibility with existing RAG infrastructure
- **One-Click Deployment**: All infrastructure must be deployable via Azure Bicep/ARM templates

### IV. Code Quality Standards

- **Python Standards**: Follow PEP 8, use type hints, maintain >80% test coverage
- **Modular Design**: Separate concerns (data access, NL2SQL, visualization, orchestration)
- **Error Handling**: Comprehensive error handling with user-friendly messages
- **Documentation**: All modules must have docstrings and usage examples

### V. Testing Requirements

- **Unit Tests**: All business logic must have unit tests
- **Integration Tests**: Test data connectors with mock data
- **End-to-End Tests**: Validate complete query flow from NL to response
- **SQL Validation Tests**: Ensure generated SQL is safe and correct

### VI. Extensibility

- **Data Source Agnostic**: Design for multiple data sources (Snowflake initially, PostgreSQL, others later)
- **Visualization Extensible**: Support adding new chart types beyond bar charts
- **Orchestrator Agnostic**: Maintain compatibility with existing orchestration strategies

## Technical Boundaries

### Must Have (POC Scope)

- Snowflake data connector with secure credential management
- NL2SQL with GPT-4o and robust validation
- Bar chart generation (matplotlib/seaborn) with base64 embedding
- Chatbot UI integration with existing React frontend
- Azure AI Foundry agent service integration
- One-click Azure Bicep deployment

### Nice to Have (Future Phases)

- Sell-out PDF data processing
- Multiple chart types (pie, line, scatter)
- Export capabilities (Excel, PDF reports)
- Multi-language support
- Real-time data streaming

### Out of Scope (POC)

- Mobile native apps
- Offline capabilities
- Custom ERP integrations beyond Snowflake
- Advanced ML predictions
- Data write-back capabilities

## Quality Gates

### Before Planning

- [ ] Requirements are clearly defined and prioritized
- [ ] Data schema is documented and accessible
- [ ] Azure resources are identified and available
- [ ] Sample data is available for testing (50K rows OrderHistoryLine CSV)

### Before Implementation

- [ ] Technical plan reviewed and approved
- [ ] Dependencies identified and compatible
- [ ] Security measures documented
- [ ] Test strategy defined

### Before Deployment

- [ ] All tests passing (unit, integration, e2e)
- [ ] Security review completed
- [ ] Documentation complete
- [ ] One-click deployment validated

## Governance

This constitution supersedes all other development practices. Any amendments require:
1. Documentation of the change and rationale
2. Review and approval by project stakeholders
3. Migration plan for affected components

All pull requests and code reviews must verify compliance with these principles.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-04 | Use Azure AI Foundry over Copilot Studio | Complex NL2SQL and custom visualization requires AI Foundry's flexibility |
| 2026-02-04 | Snowflake as initial data source | User data already in Snowflake, proven connector patterns available |
| 2026-02-04 | GPT-4o for NL2SQL | Best performance for complex SQL generation tasks |
| 2026-02-04 | matplotlib for visualizations | Python-native, well-documented, base64 embedding support |
| 2026-02-04 | Separate POC repository | Significant architectural changes warrant isolation from main codebase |

**Version**: 1.0 | **Ratified**: 2026-02-04 | **Last Amended**: 2026-02-04
