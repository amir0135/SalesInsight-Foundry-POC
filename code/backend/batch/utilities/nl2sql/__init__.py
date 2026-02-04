"""
NL2SQL Engine module for SalesInsight POC.

This module provides natural language to SQL conversion capabilities
using Azure OpenAI GPT-4o with security validation and business glossary support.
"""

from .sql_generator import NL2SQLGenerator, NL2SQLConfig, NL2SQLError, GeneratedQuery
from .query_validator import (
    QueryValidator,
    ValidationResult,
    ValidationError,
    SecurityViolationError,
)
from .prompt_builder import PromptBuilder, PromptConfig

__all__ = [
    # SQL Generator
    "NL2SQLGenerator",
    "NL2SQLConfig",
    "NL2SQLError",
    "GeneratedQuery",
    # Query Validator
    "QueryValidator",
    "ValidationResult",
    "ValidationError",
    "SecurityViolationError",
    # Prompt Builder
    "PromptBuilder",
    "PromptConfig",
]
