"""
Unit tests for NL2SQL SQL Generator.

Tests the SQL generation, prompt building, and response parsing.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from backend.batch.utilities.nl2sql.sql_generator import (
    NL2SQLGenerator,
    NL2SQLConfig,
    GeneratedQuery,
    NL2SQLError,
)
from backend.batch.utilities.nl2sql.prompt_builder import (
    PromptBuilder,
    PromptConfig,
    BusinessGlossary,
)


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI response."""
    return {
        "content": json.dumps({
            "sql": "SELECT ItemNo, SUM(NetINV) as Revenue FROM OrderHistoryLine GROUP BY ItemNo ORDER BY Revenue DESC LIMIT 10;",
            "explanation": "This query retrieves the top 10 products by total revenue.",
            "parameters": {},
            "confidence": 0.95,
        }),
        "model": "gpt-4o",
        "tokens": 150,
    }


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Create a mock Azure OpenAI client."""
    client = Mock()
    
    # Create mock response structure
    mock_choice = Mock()
    mock_choice.message.content = mock_openai_response["content"]
    
    mock_usage = Mock()
    mock_usage.total_tokens = mock_openai_response["tokens"]
    
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    mock_response.model = mock_openai_response["model"]
    mock_response.usage = mock_usage
    
    client.chat.completions.create.return_value = mock_response
    
    return client


@pytest.fixture
def generator(mock_openai_client):
    """Create a generator with mocked OpenAI client."""
    with patch("backend.batch.utilities.nl2sql.sql_generator.EnvHelper"):
        config = NL2SQLConfig(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1024,
        )
        return NL2SQLGenerator(config=config, openai_client=mock_openai_client)


@pytest.fixture
def schema_context():
    """Sample schema context for tests."""
    return """
## Available Database Schema

### Table: OrderHistoryLine
Row count: ~50,000

Columns:
  - ItemNo (VARCHAR) NOT NULL
  - ItemDescription (VARCHAR)
  - CustomerNo (VARCHAR)
  - CustomerName (VARCHAR)
  - NetINV (DECIMAL) -- Net invoice amount
  - GrossINV (DECIMAL) -- Gross invoice amount
  - FiscalYear (INTEGER)
  - FiscalQuarter (VARCHAR)
  - Region (VARCHAR)
"""


@pytest.fixture
def system_prompt():
    """Sample system prompt for tests."""
    return """You are an expert SQL analyst. Generate SQL queries to answer questions about sales data.
Respond with valid JSON containing: sql, explanation, parameters, confidence."""


class TestNL2SQLGeneratorBasic:
    """Basic tests for NL2SQLGenerator."""

    def test_generate_returns_query(self, generator, schema_context, system_prompt):
        """Test that generate returns a GeneratedQuery object."""
        result = generator.generate(
            question="What are the top 10 products by revenue?",
            schema_context=schema_context,
            system_prompt=system_prompt,
        )
        
        assert isinstance(result, GeneratedQuery)
        assert result.sql is not None
        assert len(result.sql) > 0

    def test_generate_includes_explanation(self, generator, schema_context, system_prompt):
        """Test that generated query includes explanation."""
        result = generator.generate(
            question="What are the top 10 products by revenue?",
            schema_context=schema_context,
            system_prompt=system_prompt,
        )
        
        assert result.explanation is not None

    def test_generate_includes_metadata(self, generator, schema_context, system_prompt):
        """Test that generated query includes metadata."""
        result = generator.generate(
            question="What are the top 10 products by revenue?",
            schema_context=schema_context,
            system_prompt=system_prompt,
        )
        
        assert result.model_used is not None
        assert result.tokens_used >= 0
        assert result.generation_time_ms > 0

    def test_generate_stores_original_question(self, generator, schema_context, system_prompt):
        """Test that original question is stored in result."""
        question = "What are the top 10 products by revenue?"
        result = generator.generate(
            question=question,
            schema_context=schema_context,
            system_prompt=system_prompt,
        )
        
        assert result.original_question == question


class TestNL2SQLGeneratorSQLCleaning:
    """Tests for SQL cleaning functionality."""

    def test_removes_markdown_code_blocks(self, generator):
        """Test that markdown code blocks are removed."""
        sql = "```sql\nSELECT * FROM table;\n```"
        cleaned = generator._clean_sql(sql)
        
        assert "```" not in cleaned
        assert "SELECT" in cleaned

    def test_normalizes_whitespace(self, generator):
        """Test that whitespace is normalized."""
        sql = "SELECT    *   FROM    table   LIMIT   10"
        cleaned = generator._clean_sql(sql)
        
        assert "    " not in cleaned  # No multiple spaces

    def test_adds_semicolon(self, generator):
        """Test that semicolon is added if missing."""
        sql = "SELECT * FROM table LIMIT 10"
        cleaned = generator._clean_sql(sql)
        
        assert cleaned.endswith(";")

    def test_preserves_existing_semicolon(self, generator):
        """Test that existing semicolon is preserved."""
        sql = "SELECT * FROM table LIMIT 10;"
        cleaned = generator._clean_sql(sql)
        
        assert cleaned.count(";") == 1


class TestNL2SQLGeneratorResponseParsing:
    """Tests for response parsing."""

    def test_parses_valid_json_response(self, generator):
        """Test parsing of valid JSON response."""
        response = {
            "content": json.dumps({
                "sql": "SELECT * FROM table;",
                "explanation": "Test query",
                "confidence": 0.9,
            }),
            "model": "gpt-4o",
            "tokens": 100,
        }
        
        result = generator._parse_response(response, "Test question")
        
        assert result.sql == "SELECT * FROM table;"
        assert result.explanation == "Test query"
        assert result.confidence_score == 0.9

    def test_extracts_sql_from_markdown(self, generator):
        """Test extraction of SQL from markdown response."""
        response = {
            "content": "Here's the SQL:\n```sql\nSELECT * FROM table;\n```",
            "model": "gpt-4o",
            "tokens": 100,
        }
        
        result = generator._parse_response(response, "Test question")
        
        assert "SELECT" in result.sql

    def test_raises_on_empty_sql(self, generator):
        """Test that empty SQL raises error."""
        response = {
            "content": json.dumps({"sql": "", "explanation": "No query"}),
            "model": "gpt-4o",
            "tokens": 100,
        }
        
        with pytest.raises(NL2SQLError):
            generator._parse_response(response, "Test question")


class TestNL2SQLGeneratorWithRetry:
    """Tests for retry functionality."""

    def test_retry_on_failure(self, mock_openai_client):
        """Test that generator retries on failure."""
        # First call fails, second succeeds
        mock_choice_success = Mock()
        mock_choice_success.message.content = json.dumps({
            "sql": "SELECT * FROM table LIMIT 10;",
            "explanation": "Success",
        })
        
        mock_response_success = Mock()
        mock_response_success.choices = [mock_choice_success]
        mock_response_success.model = "gpt-4o"
        mock_response_success.usage = Mock(total_tokens=100)
        
        # Fail first, succeed second
        mock_openai_client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            mock_response_success,
        ]
        
        with patch("backend.batch.utilities.nl2sql.sql_generator.EnvHelper"):
            config = NL2SQLConfig(max_retries=3)
            generator = NL2SQLGenerator(config=config, openai_client=mock_openai_client)
            
            result = generator.generate_with_retry(
                question="Test",
                schema_context="Schema",
                system_prompt="Prompt",
            )
            
            assert result.sql is not None

    def test_raises_after_max_retries(self, mock_openai_client):
        """Test that error is raised after max retries exceeded."""
        mock_openai_client.chat.completions.create.side_effect = Exception("Persistent error")
        
        with patch("backend.batch.utilities.nl2sql.sql_generator.EnvHelper"):
            config = NL2SQLConfig(max_retries=2)
            generator = NL2SQLGenerator(config=config, openai_client=mock_openai_client)
            
            with pytest.raises(NL2SQLError):
                generator.generate_with_retry(
                    question="Test",
                    schema_context="Schema",
                    system_prompt="Prompt",
                )


class TestGeneratedQuery:
    """Tests for GeneratedQuery dataclass."""

    def test_to_dict(self):
        """Test GeneratedQuery serialization."""
        query = GeneratedQuery(
            sql="SELECT * FROM table;",
            explanation="Test query",
            parameters={"year": 2024},
            confidence_score=0.95,
            original_question="Test question",
            generation_time_ms=150.5,
            model_used="gpt-4o",
            tokens_used=100,
        )
        
        d = query.to_dict()
        
        assert d["sql"] == "SELECT * FROM table;"
        assert d["explanation"] == "Test query"
        assert d["parameters"] == {"year": 2024}
        assert d["confidence_score"] == 0.95
        assert d["generation_time_ms"] == 150.5


class TestPromptBuilder:
    """Tests for PromptBuilder."""

    @pytest.fixture
    def prompt_builder(self):
        """Create a prompt builder with test glossary."""
        glossary = BusinessGlossary(
            term_mappings={
                "turnover": "SUM(NetINV)",
                "revenue": "SUM(GrossINV)",
            },
            ranking_terms={
                "top": "DESC",
                "bottom": "ASC",
            },
            time_period_mappings={
                "this year": "FiscalYear = 2024",
                "last year": "FiscalYear = 2023",
            },
        )
        
        builder = PromptBuilder(config=PromptConfig())
        builder.glossary = glossary
        return builder

    def test_build_system_prompt(self, prompt_builder):
        """Test system prompt building."""
        schema_context = "Table: OrderHistoryLine"
        
        prompt = prompt_builder.build_system_prompt(schema_context)
        
        assert "OrderHistoryLine" in prompt
        assert "SQL" in prompt

    def test_build_user_prompt(self, prompt_builder):
        """Test user prompt building."""
        question = "What is the total turnover?"
        
        prompt = prompt_builder.build_user_prompt(question)
        
        assert question in prompt
        # Should include term expansion hint
        assert "turnover" in prompt.lower()

    def test_format_business_context(self, prompt_builder):
        """Test business context formatting."""
        context = prompt_builder._format_business_context()
        
        assert "turnover" in context
        assert "SUM(NetINV)" in context

    def test_expand_terms(self, prompt_builder):
        """Test term expansion in questions."""
        question = "Show me the total turnover this year"
        
        expanded = prompt_builder._expand_terms(question)
        
        assert "turnover" in expanded
        # Should add hints about term meaning

    def test_format_examples(self, prompt_builder):
        """Test few-shot example formatting."""
        examples = prompt_builder._format_examples()
        
        assert "Example" in examples
        assert "SELECT" in examples


class TestNL2SQLConfig:
    """Tests for NL2SQLConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NL2SQLConfig()
        
        assert config.model == "gpt-4o"
        assert config.temperature == 0.0
        assert config.max_tokens == 1024
        assert config.max_retries == 3

    def test_custom_values(self):
        """Test custom configuration values."""
        config = NL2SQLConfig(
            model="gpt-4",
            temperature=0.5,
            max_tokens=2048,
        )
        
        assert config.model == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
