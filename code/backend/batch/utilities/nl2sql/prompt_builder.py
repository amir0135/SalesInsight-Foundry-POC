"""
Prompt Builder for NL2SQL generation.

This module provides templates and utilities for building prompts
that include schema context, business glossary, and instructions
for the LLM to generate accurate SQL.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PromptConfig:
    """Configuration for prompt building."""

    include_examples: bool = True
    include_business_context: bool = True
    max_schema_tables: int = 10
    max_examples: int = 3


@dataclass
class BusinessGlossary:
    """Business terminology and mappings loaded from config."""

    term_mappings: dict[str, str] = field(default_factory=dict)
    ranking_terms: dict[str, str] = field(default_factory=dict)
    fiscal_years: dict[str, dict] = field(default_factory=dict)
    time_period_mappings: dict[str, str] = field(default_factory=dict)
    entity_synonyms: dict[str, list[str]] = field(default_factory=dict)
    column_display_names: dict[str, str] = field(default_factory=dict)


# Default system prompt template
DEFAULT_SYSTEM_PROMPT = """You are an expert SQL analyst specializing in sales data analytics.
Your task is to convert natural language questions into accurate, secure SQL queries.

## Important Rules:
1. Generate ONLY SELECT queries - no INSERT, UPDATE, DELETE, or DDL statements
2. Always use parameterized values for user-provided filters
3. Include a LIMIT clause to prevent excessive data retrieval
4. Use table and column aliases for readability
5. Apply appropriate aggregations (SUM, AVG, COUNT) based on the question
6. Consider fiscal year boundaries when dealing with date ranges
7. Return results that directly answer the user's question

## Output Format:
You MUST respond with valid JSON in this exact format:
{
  "sql": "YOUR SQL QUERY HERE",
  "explanation": "Brief explanation of what the query does",
  "parameters": {"param_name": "value"},
  "confidence": 0.95
}

## Business Context:
{business_context}

## Database Schema:
{schema_context}
"""

# Few-shot examples for better generation
FEW_SHOT_EXAMPLES = [
    {
        "question": "What are the top 10 products by turnover this year?",
        "sql": """SELECT
    ItemNo,
    ItemDescription,
    SUM(NetINV) as TotalTurnover
FROM OrderHistoryLine
WHERE FiscalYear = :current_year
GROUP BY ItemNo, ItemDescription
ORDER BY TotalTurnover DESC
LIMIT 10;""",
        "explanation": "Aggregates net invoice amounts by product and returns top 10 by total turnover",
    },
    {
        "question": "Show me customer revenue breakdown by region",
        "sql": """SELECT
    Region,
    COUNT(DISTINCT CustomerNo) as CustomerCount,
    SUM(NetINV) as TotalRevenue
FROM OrderHistoryLine
GROUP BY Region
ORDER BY TotalRevenue DESC
LIMIT 100;""",
        "explanation": "Groups revenue by region with customer count for geographic analysis",
    },
    {
        "question": "Compare sales performance between Q1 and Q2",
        "sql": """SELECT
    FiscalQuarter,
    SUM(NetINV) as TotalSales,
    COUNT(DISTINCT OrderNo) as OrderCount,
    AVG(NetINV) as AvgOrderValue
FROM OrderHistoryLine
WHERE FiscalQuarter IN ('Q1', 'Q2')
    AND FiscalYear = :current_year
GROUP BY FiscalQuarter
ORDER BY FiscalQuarter
LIMIT 100;""",
        "explanation": "Compares key sales metrics between fiscal quarters Q1 and Q2",
    },
]


class PromptBuilder:
    """
    Builds prompts for NL2SQL generation with context injection.

    This class assembles prompts that include:
    - System instructions for the LLM
    - Database schema context
    - Business glossary for term translation
    - Few-shot examples for better accuracy
    """

    def __init__(
        self,
        config: Optional[PromptConfig] = None,
        glossary_path: Optional[str] = None,
        system_prompt_template: Optional[str] = None,
    ):
        """
        Initialize the prompt builder.

        Args:
            config: Optional prompt configuration
            glossary_path: Path to business glossary YAML file
            system_prompt_template: Optional custom system prompt template
        """
        self.config = config or PromptConfig()
        self.system_prompt_template = system_prompt_template or DEFAULT_SYSTEM_PROMPT
        self.examples = FEW_SHOT_EXAMPLES

        # Load business glossary
        if glossary_path:
            self.glossary = self._load_glossary(glossary_path)
        else:
            # Try default location
            default_path = (
                Path(__file__).parent / "config" / "business_glossary.yaml"
            )
            if default_path.exists():
                self.glossary = self._load_glossary(str(default_path))
            else:
                self.glossary = BusinessGlossary()

        logger.info(
            f"PromptBuilder initialized with {len(self.glossary.term_mappings)} "
            f"term mappings"
        )

    def _load_glossary(self, path: str) -> BusinessGlossary:
        """Load business glossary from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            return BusinessGlossary(
                term_mappings=data.get("term_mappings", {}),
                ranking_terms=data.get("ranking_terms", {}),
                fiscal_years=data.get("fiscal_years", {}),
                time_period_mappings=data.get("time_period_mappings", {}),
                entity_synonyms=data.get("entity_synonyms", {}),
                column_display_names=data.get("column_display_names", {}),
            )
        except Exception as e:
            logger.warning(f"Failed to load glossary from {path}: {e}")
            return BusinessGlossary()

    def build_system_prompt(
        self,
        schema_context: str,
        business_context: Optional[str] = None,
    ) -> str:
        """
        Build the system prompt with schema and business context.

        Args:
            schema_context: Database schema description
            business_context: Optional business glossary context

        Returns:
            Complete system prompt string
        """
        if business_context is None:
            business_context = self._format_business_context()

        prompt = self.system_prompt_template.format(
            schema_context=schema_context,
            business_context=business_context,
        )

        # Add few-shot examples if enabled
        if self.config.include_examples:
            examples_text = self._format_examples()
            prompt += f"\n\n## Examples:\n{examples_text}"

        return prompt

    def build_user_prompt(
        self,
        question: str,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        Build the user prompt with the question.

        Args:
            question: The natural language question
            additional_context: Optional additional context

        Returns:
            User prompt string
        """
        # Pre-process the question with glossary term expansion
        processed_question = self._expand_terms(question)

        parts = [f"## Question:\n{processed_question}"]

        if additional_context:
            parts.append(f"\n## Additional Context:\n{additional_context}")

        parts.append(
            "\n## Instructions:\n"
            "Generate a SQL query to answer this question. "
            "Respond with valid JSON containing 'sql', 'explanation', "
            "'parameters', and 'confidence' fields."
        )

        return "\n".join(parts)

    def _format_business_context(self) -> str:
        """Format business glossary as context string."""
        parts = []

        if self.glossary.term_mappings:
            parts.append("### Business Terms:")
            for term, sql_expr in self.glossary.term_mappings.items():
                parts.append(f"- '{term}' → {sql_expr}")

        if self.glossary.ranking_terms:
            parts.append("\n### Ranking Terms:")
            for term, order in self.glossary.ranking_terms.items():
                parts.append(f"- '{term}' → ORDER BY ... {order}")

        if self.glossary.time_period_mappings:
            parts.append("\n### Time Periods:")
            for term, filter_expr in self.glossary.time_period_mappings.items():
                parts.append(f"- '{term}' → {filter_expr}")

        if self.glossary.fiscal_years:
            parts.append("\n### Fiscal Year Information:")
            for year_name, info in self.glossary.fiscal_years.items():
                start = info.get("start", "")
                end = info.get("end", "")
                parts.append(f"- {year_name}: {start} to {end}")

        if self.glossary.entity_synonyms:
            parts.append("\n### Entity Synonyms:")
            for entity, synonyms in self.glossary.entity_synonyms.items():
                parts.append(f"- {entity}: {', '.join(synonyms)}")

        return "\n".join(parts) if parts else "No specific business context available."

    def _format_examples(self) -> str:
        """Format few-shot examples for the prompt."""
        examples_to_use = self.examples[: self.config.max_examples]

        parts = []
        for i, example in enumerate(examples_to_use, 1):
            parts.append(f"### Example {i}:")
            parts.append(f"Question: {example['question']}")
            parts.append(f"SQL:\n```sql\n{example['sql']}\n```")
            parts.append(f"Explanation: {example['explanation']}\n")

        return "\n".join(parts)

    def _expand_terms(self, question: str) -> str:
        """Expand business terms in the question for clarity."""
        expanded = question

        # Add term hints as comments (don't modify the actual question)
        hints = []

        for term, sql_expr in self.glossary.term_mappings.items():
            if term.lower() in question.lower():
                hints.append(f"Note: '{term}' = {sql_expr}")

        for entity, synonyms in self.glossary.entity_synonyms.items():
            for synonym in synonyms:
                if synonym.lower() in question.lower():
                    hints.append(f"Note: '{synonym}' refers to {entity}")

        if hints:
            expanded += "\n\n" + "\n".join(hints)

        return expanded

    def get_schema_context_template(self) -> str:
        """Get a template for schema context formatting."""
        return """## Database Schema

### Table: {table_name}
Description: {description}
Row Count: ~{row_count:,}

Columns:
{columns}

### Sample Values:
{sample_values}
"""

    def add_example(
        self,
        question: str,
        sql: str,
        explanation: str,
    ) -> None:
        """Add a new few-shot example."""
        self.examples.append({
            "question": question,
            "sql": sql,
            "explanation": explanation,
        })
        logger.info(f"Added new example: {question[:50]}...")

    def set_custom_system_prompt(self, template: str) -> None:
        """Set a custom system prompt template."""
        # Validate template has required placeholders
        required = ["{schema_context}", "{business_context}"]
        for placeholder in required:
            if placeholder not in template:
                raise ValueError(
                    f"Template must contain {placeholder} placeholder"
                )

        self.system_prompt_template = template
        logger.info("Custom system prompt template set")
