"""
SQL Generator for NL2SQL conversion using Azure OpenAI GPT-4o.

This module provides the core NL2SQL generation capability, converting
natural language queries into validated SQL statements.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from openai import AzureOpenAI

from ..helpers.env_helper import EnvHelper

logger = logging.getLogger(__name__)


@dataclass
class NL2SQLConfig:
    """Configuration for NL2SQL generation."""

    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout: float = 30.0
    max_retries: int = 3
    include_explanation: bool = True


@dataclass
class GeneratedQuery:
    """Result of NL2SQL generation."""

    sql: str
    explanation: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence_score: Optional[float] = None
    original_question: str = ""
    generation_time_ms: float = 0.0
    model_used: str = ""
    tokens_used: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "sql": self.sql,
            "explanation": self.explanation,
            "parameters": self.parameters,
            "confidence_score": self.confidence_score,
            "original_question": self.original_question,
            "generation_time_ms": self.generation_time_ms,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
        }


class NL2SQLGenerator:
    """
    Generates SQL from natural language using Azure OpenAI GPT-4o.

    This class handles the core NL2SQL conversion, including:
    - Schema context injection
    - Business glossary term mapping
    - Parameterized query generation
    - Confidence scoring
    """

    def __init__(
        self,
        config: Optional[NL2SQLConfig] = None,
        openai_client: Optional[AzureOpenAI] = None,
    ):
        """
        Initialize the NL2SQL generator.

        Args:
            config: Optional configuration for generation
            openai_client: Optional pre-configured OpenAI client
        """
        self.config = config or NL2SQLConfig()
        self.env_helper = EnvHelper()

        if openai_client:
            self.client = openai_client
        else:
            self.client = self._create_openai_client()

        logger.info(
            f"NL2SQLGenerator initialized with model: {self.config.model}"
        )

    def _create_openai_client(self) -> AzureOpenAI:
        """Create Azure OpenAI client from environment configuration."""
        return AzureOpenAI(
            api_key=self.env_helper.AZURE_OPENAI_API_KEY,
            api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
            azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
        )

    def generate(
        self,
        question: str,
        schema_context: str,
        system_prompt: str,
        business_context: Optional[str] = None,
    ) -> GeneratedQuery:
        """
        Generate SQL from a natural language question.

        Args:
            question: The natural language question
            schema_context: Database schema description for context
            system_prompt: System prompt with instructions
            business_context: Optional business glossary context

        Returns:
            GeneratedQuery with SQL and metadata
        """
        start_time = datetime.now()

        # Build the full prompt
        full_context = self._build_context(
            schema_context, business_context
        )

        try:
            response = self._call_openai(
                question=question,
                context=full_context,
                system_prompt=system_prompt,
            )

            # Parse the response
            generated = self._parse_response(response, question)

            # Calculate generation time
            generation_time = (datetime.now() - start_time).total_seconds() * 1000
            generated.generation_time_ms = generation_time

            logger.info(
                f"Generated SQL in {generation_time:.0f}ms for question: "
                f"{question[:50]}..."
            )

            return generated

        except Exception as e:
            logger.error(f"NL2SQL generation failed: {e}")
            raise NL2SQLError(f"Failed to generate SQL: {e}") from e

    def _build_context(
        self,
        schema_context: str,
        business_context: Optional[str],
    ) -> str:
        """Build combined context for the LLM."""
        parts = [schema_context]

        if business_context:
            parts.append("\n## Business Context\n")
            parts.append(business_context)

        return "\n".join(parts)

    def _call_openai(
        self,
        question: str,
        context: str,
        system_prompt: str,
    ) -> dict:
        """Call Azure OpenAI API for SQL generation."""
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{context}\n\n## Question\n{question}",
            },
        ]

        response = self.client.chat.completions.create(
            model=self.env_helper.AZURE_OPENAI_MODEL,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            response_format={"type": "json_object"},
        )

        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "tokens": response.usage.total_tokens if response.usage else 0,
        }

    def _parse_response(self, response: dict, question: str) -> GeneratedQuery:
        """Parse the OpenAI response into a GeneratedQuery."""
        content = response.get("content", "")

        try:
            # Parse JSON response
            parsed = json.loads(content)

            sql = parsed.get("sql", "").strip()
            if not sql:
                raise NL2SQLError("No SQL generated in response")

            # Extract parameters if present
            parameters = parsed.get("parameters", {})

            # Clean up the SQL
            sql = self._clean_sql(sql)

            return GeneratedQuery(
                sql=sql,
                explanation=parsed.get("explanation"),
                parameters=parameters,
                confidence_score=parsed.get("confidence", None),
                original_question=question,
                model_used=response.get("model", self.config.model),
                tokens_used=response.get("tokens", 0),
            )

        except json.JSONDecodeError:
            # Try to extract SQL from non-JSON response
            sql = self._extract_sql_from_text(content)
            if sql:
                return GeneratedQuery(
                    sql=sql,
                    original_question=question,
                    model_used=response.get("model", self.config.model),
                    tokens_used=response.get("tokens", 0),
                )
            raise NL2SQLError(f"Failed to parse response: {content[:100]}")

    def _clean_sql(self, sql: str) -> str:
        """Clean and normalize SQL statement."""
        # Remove markdown code blocks if present
        sql = re.sub(r"```sql\s*", "", sql)
        sql = re.sub(r"```\s*", "", sql)

        # Normalize whitespace
        sql = " ".join(sql.split())

        # Ensure it ends with semicolon
        if not sql.endswith(";"):
            sql += ";"

        return sql

    def _extract_sql_from_text(self, text: str) -> Optional[str]:
        """Attempt to extract SQL from free-form text response."""
        # Look for SQL between code blocks
        pattern = r"```sql\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return self._clean_sql(match.group(1))

        # Look for SELECT statement
        pattern = r"(SELECT\s+.*?;)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return self._clean_sql(match.group(1))

        return None

    def generate_with_retry(
        self,
        question: str,
        schema_context: str,
        system_prompt: str,
        business_context: Optional[str] = None,
        validation_feedback: Optional[str] = None,
    ) -> GeneratedQuery:
        """
        Generate SQL with retry logic for validation failures.

        Args:
            question: The natural language question
            schema_context: Database schema description
            system_prompt: System prompt with instructions
            business_context: Optional business glossary context
            validation_feedback: Optional feedback from previous validation failure

        Returns:
            GeneratedQuery with SQL and metadata
        """
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                # Add validation feedback to the question if retrying
                enhanced_question = question
                if validation_feedback and attempt > 0:
                    enhanced_question = (
                        f"{question}\n\n"
                        f"Note: Previous attempt was invalid. "
                        f"Error: {validation_feedback}"
                    )

                result = self.generate(
                    question=enhanced_question,
                    schema_context=schema_context,
                    system_prompt=system_prompt,
                    business_context=business_context,
                )

                return result

            except NL2SQLError as e:
                last_error = e
                logger.warning(
                    f"NL2SQL generation attempt {attempt + 1} failed: {e}"
                )
                continue

        raise NL2SQLError(
            f"Failed to generate SQL after {self.config.max_retries} attempts: "
            f"{last_error}"
        )


class NL2SQLError(Exception):
    """Exception raised when NL2SQL generation fails."""

    pass
