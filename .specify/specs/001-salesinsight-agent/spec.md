# Feature Specification: SalesInsight AI Agent

**Feature Branch**: `001-salesinsight-agent`  
**Created**: 2026-02-04  
**Status**: Draft  
**Input**: POC Requirements Document for AI-powered sales data analytics agent

## Executive Summary

Develop an AI agent that provides analytical insights from sales data through a conversational interface. The solution enables sales teams to query complex business data using natural language, focusing on "sell-in" data with both textual summaries and visual bar charts.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query Best Sold Styles (Priority: P1)

As a sales representative, I want to ask "What are the best sold styles?" so that I can quickly identify top-performing products for my sales preparation.

**Why this priority**: Core value proposition - answering the most common sales question with minimal friction.

**Independent Test**: Can be tested by sending the natural language query to the agent and validating that it returns a ranked list of styles by sales volume/revenue.

**Acceptance Scenarios**:

1. **Given** the agent is connected to Snowflake with OrderHistoryLine data, **When** I ask "What are the best sold styles?", **Then** I receive a text summary of top 10 styles ranked by quantity sold
2. **Given** the query returns results, **When** the data contains more than 5 items, **Then** a bar chart visualization is included in the response
3. **Given** the query returns results, **When** I specify a time period like "this year", **Then** the results are filtered to that period

---

### User Story 2 - Query Turnover by Market and Brand (Priority: P1)

As a sales manager, I want to ask "What is the turnover in current FY in France – narrowed into Brand X?" so that I can understand market-specific brand performance.

**Why this priority**: Critical for regional sales planning and brand strategy discussions.

**Independent Test**: Can be tested by querying with market and brand filters, validating SQL generation includes correct WHERE clauses.

**Acceptance Scenarios**:

1. **Given** valid market and brand parameters, **When** I ask "What is the turnover in FY 25/26 in France for Brand X?", **Then** I receive the total Net INV value with currency formatting
2. **Given** the market or brand doesn't exist, **When** I submit the query, **Then** I receive a friendly message suggesting valid alternatives
3. **Given** multiple brands are requested, **When** I ask "Compare turnover for Brand X and Brand Y in France", **Then** I receive a comparison with a grouped bar chart

---

### User Story 3 - Query Collection-Specific Sales (Priority: P1)

As a sales representative, I want to ask "What was the turnover on collection COL1 2025 in France?" so that I can prepare for collection review meetings.

**Why this priority**: Essential for collection performance tracking and seasonal planning.

**Independent Test**: Can be tested by querying with collection filter, validating correct aggregation of Net INV.

**Acceptance Scenarios**:

1. **Given** a valid collection code, **When** I ask about collection turnover, **Then** I receive the total turnover for that collection
2. **Given** I also request breakdown, **When** I ask "breakdown by category", **Then** I receive category-level details with visualization
3. **Given** the collection code is ambiguous, **When** I ask the query, **Then** the agent asks for clarification

---

### User Story 4 - Detailed Style List by Customer (Priority: P2)

As a sales representative, I want to ask "Give me a list of styles we sold to [Customer] on collection COL1 2025. Include colour and variant per style and quantity per variant" so that I can prepare detailed customer reviews.

**Why this priority**: Important for account-level preparation but more complex query.

**Independent Test**: Can be tested by querying with customer filter and validating the response includes style, color, variant, and quantity columns.

**Acceptance Scenarios**:

1. **Given** a valid customer/holding name, **When** I request the detailed list, **Then** I receive a structured table with Style, Color, Variant, Quantity
2. **Given** the result set is large (>50 rows), **When** the query completes, **Then** the response includes pagination guidance or a summary with option to export
3. **Given** the customer name is partial, **When** I submit the query, **Then** the agent suggests matching customers

---

### User Story 5 - Category Analysis (Priority: P2)

As a category manager, I want to ask "Give me an overview of the best sold dresses for the category Dresses" so that I can analyze category performance.

**Why this priority**: Enables category-specific insights for product strategy.

**Independent Test**: Can be tested by querying with category filter and validating proper aggregation and ranking.

**Acceptance Scenarios**:

1. **Given** a valid category name, **When** I ask for best sold items in category, **Then** I receive a ranked list with quantities and revenue
2. **Given** the category has multiple subcategories, **When** I ask for the overview, **Then** the summary includes subcategory breakdown
3. **Given** the result is suitable for visualization, **When** returned, **Then** a bar chart shows top 10 items in category

---

### User Story 6 - Fiscal Year Total Turnover (Priority: P2)

As a sales director, I want to ask "What is the total turnover (Net INV) in France this FY (FY 25/26)?" so that I can track overall market performance.

**Why this priority**: Executive-level reporting need.

**Independent Test**: Can be tested by querying with fiscal year and market filter, validating correct date range calculation.

**Acceptance Scenarios**:

1. **Given** a valid fiscal year reference, **When** I ask for total turnover, **Then** I receive the aggregated Net INV with proper currency formatting
2. **Given** the fiscal year spans calendar years, **When** the query executes, **Then** the date filtering correctly handles FY boundaries
3. **Given** I ask for comparison, **When** I say "compared to last FY", **Then** I receive both values with percentage change

---

### User Story 7 - Bar Chart Visualization (Priority: P1)

As a sales user, I want to see bar charts alongside text answers so that I can quickly visualize data patterns and share insights with colleagues.

**Why this priority**: Explicit user requirement for visual data representation.

**Independent Test**: Can be tested by submitting any query that returns rankable data and validating image is embedded in response.

**Acceptance Scenarios**:

1. **Given** a query returns ranked/categorical data, **When** results contain >3 items, **Then** a bar chart is automatically generated
2. **Given** the bar chart is generated, **When** embedded in response, **Then** it renders correctly in the chat interface
3. **Given** the data has labels, **When** chart is created, **Then** axes are properly labeled with legend if needed

---

### User Story 8 - Delivery Month Analysis (Priority: P3)

As a logistics coordinator, I want to ask about sales by delivery month so that I can plan inventory and logistics.

**Why this priority**: Secondary use case for operations planning.

**Independent Test**: Can be tested by querying with delivery month grouping.

**Acceptance Scenarios**:

1. **Given** I ask "Show sales by delivery month for Q1", **When** query executes, **Then** results are grouped and ordered by delivery month
2. **Given** monthly data is returned, **When** visualization is appropriate, **Then** a bar chart shows month-over-month comparison

---

### Edge Cases

- What happens when Snowflake connection fails?
  - Display friendly error message with retry option
- How does system handle queries with no results?
  - Return "No data found matching your criteria" with suggestions
- What if generated SQL is invalid?
  - Log error, attempt to regenerate, display fallback message
- How does system handle ambiguous entity names?
  - Ask for clarification with suggestions from schema
- What if chart generation fails?
  - Return text-only response with note about visualization unavailability
- What if query would return >100K rows?
  - Apply default limit, inform user, suggest refinement

---

## Requirements *(mandatory)*

### Functional Requirements

#### Data Integration

- **FR-001**: System MUST connect to Snowflake data warehouse securely using service account credentials
- **FR-002**: System MUST support schema discovery to understand available tables, columns, and relationships
- **FR-003**: System MUST handle the OrderHistoryLine dataset (50K+ rows) with acceptable performance
- **FR-004**: System MUST cache schema metadata to improve query generation performance

#### Natural Language to SQL (NL2SQL)

- **FR-005**: System MUST convert natural language queries to valid Snowflake SQL using GPT-4o
- **FR-006**: System MUST validate generated SQL before execution (syntax, safety, allowlist)
- **FR-007**: System MUST use parameterized queries to prevent SQL injection
- **FR-008**: System MUST implement table and column allowlists to restrict data access
- **FR-009**: System MUST handle fiscal year calculations (e.g., FY 25/26 = July 2025 - June 2026)
- **FR-010**: System MUST recognize entity synonyms (e.g., "turnover" = "Net INV")

#### Visualization

- **FR-011**: System MUST generate bar charts using matplotlib/seaborn for ranked data
- **FR-012**: System MUST embed charts as base64 images in API responses
- **FR-013**: System MUST include proper axis labels, titles, and legends on charts
- **FR-014**: System MUST decide when visualization is appropriate based on query type

#### User Interface

- **FR-015**: System MUST provide a chatbot interface for natural language interaction
- **FR-016**: System MUST render both text and image responses in the chat UI
- **FR-017**: System MUST display loading indicators during query processing
- **FR-018**: System MUST support conversation history for context

#### Agent Orchestration

- **FR-019**: System MUST use Azure AI Foundry Agent Service for tool orchestration
- **FR-020**: System MUST expose data query and visualization as callable tools
- **FR-021**: System MUST log agent decisions and tool invocations for transparency
- **FR-022**: System MUST integrate with existing orchestration strategies (Semantic Kernel, LangChain)

#### Deployment

- **FR-023**: System MUST be deployable to Azure via one-click deployment (Bicep/ARM)
- **FR-024**: System MUST integrate with Azure Monitor and Application Insights
- **FR-025**: System MUST support the existing CI/CD pipeline structure

### Non-Functional Requirements

- **NFR-001**: Query response time MUST be < 10 seconds for typical queries
- **NFR-002**: System MUST handle 10 concurrent users without degradation
- **NFR-003**: SQL generation accuracy MUST be > 90% for supported query types
- **NFR-004**: System MUST be available 99.5% during business hours
- **NFR-005**: All sensitive data MUST be encrypted in transit and at rest

---

## Key Entities

### OrderHistoryLine (Primary Data Source)

Core sales transaction data with key attributes:
- Order identifiers and line numbers
- Style, Color, Variant information
- Customer/Holding identification
- Market/Country classification
- Brand and Category hierarchy
- Collection codes and seasons
- Quantity and Net INV (invoice) values
- Delivery month and fiscal year markers

### Query Session

Represents a user's interaction session:
- Session identifier
- User context (optional, for future auth)
- Conversation history
- Query/response pairs

### Chart Response

Represents a generated visualization:
- Chart type (bar chart for POC)
- Data series and labels
- Base64 encoded image
- Metadata (title, axes labels)

---

## Clarifications Needed

| Item | Question | Impact |
|------|----------|--------|
| Fiscal Year Definition | Confirm FY 25/26 date range (July 2025 - June 2026?) | SQL date filtering logic |
| Currency Handling | Single currency or multi-currency with conversion? | Aggregation and display |
| Snowflake Credentials | Service account or OAuth for connection? | Security implementation |
| User Authentication | Required for POC or deferred? | UI and access control |
| Data Refresh Frequency | Real-time or periodic sync to Snowflake? | Caching strategy |

---

## Review & Acceptance Checklist

- [ ] All P1 user stories are clearly defined and testable
- [ ] Security requirements for SQL generation are comprehensive
- [ ] Visualization requirements are specific and achievable
- [ ] Azure AI Foundry integration approach is documented
- [ ] Deployment requirements align with one-click preference
- [ ] Edge cases are identified and handled
- [ ] Performance requirements are measurable
