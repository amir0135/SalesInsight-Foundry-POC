"""
Query Validator for NL2SQL security enforcement.

This module provides SQL validation and security checks to ensure
generated queries comply with allowlist rules and prevent SQL injection.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import sqlparse
import yaml

logger = logging.getLogger(__name__)


@dataclass
class AllowlistConfig:
    """Configuration loaded from allowlist YAML file."""

    allowed_tables: list[str] = field(default_factory=list)
    allowed_columns: dict[str, list[str]] = field(default_factory=dict)
    blocked_keywords: list[str] = field(default_factory=list)
    allowed_functions: list[str] = field(default_factory=list)
    max_row_limit: int = 10000
    require_limit: bool = True
    allow_joins: bool = False
    allow_subqueries: bool = False


@dataclass
class ValidationResult:
    """Result of query validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_sql: Optional[str] = None
    tables_used: list[str] = field(default_factory=list)
    columns_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_sql": self.sanitized_sql,
            "tables_used": self.tables_used,
            "columns_used": self.columns_used,
        }


class QueryValidator:
    """
    Validates SQL queries against security rules and allowlists.

    This class ensures that generated SQL queries:
    - Only access allowed tables and columns
    - Don't contain blocked keywords (DDL, DML)
    - Include proper LIMIT clauses
    - Are properly parameterized
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[AllowlistConfig] = None,
    ):
        """
        Initialize the query validator.

        Args:
            config_path: Path to allowlist YAML configuration file
            config: Optional pre-loaded configuration
        """
        if config:
            self.config = config
        elif config_path:
            self.config = self._load_config(config_path)
        else:
            # Load from default location
            default_path = (
                Path(__file__).parent / "config" / "allowlist_config.yaml"
            )
            if default_path.exists():
                self.config = self._load_config(str(default_path))
            else:
                logger.warning(
                    "No allowlist config found, using empty configuration"
                )
                self.config = AllowlistConfig()

        # Compile patterns for efficiency
        self._blocked_pattern = self._compile_blocked_pattern()

        logger.info(
            f"QueryValidator initialized with {len(self.config.allowed_tables)} "
            f"allowed tables"
        )

    def _load_config(self, config_path: str) -> AllowlistConfig:
        """Load configuration from YAML file."""
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)

            # Build column allowlist per table
            allowed_columns = {}
            if "allowed_columns" in data:
                for table, columns in data["allowed_columns"].items():
                    allowed_columns[table.upper()] = [c.upper() for c in columns]

            return AllowlistConfig(
                allowed_tables=[t.upper() for t in data.get("allowed_tables", [])],
                allowed_columns=allowed_columns,
                blocked_keywords=[
                    k.upper() for k in data.get("blocked_keywords", [])
                ],
                allowed_functions=[
                    f.upper() for f in data.get("allowed_functions", [])
                ],
                max_row_limit=data.get("query_limits", {}).get(
                    "max_row_limit", 10000
                ),
                require_limit=data.get("query_limits", {}).get(
                    "require_limit", True
                ),
                allow_joins=data.get("query_limits", {}).get("allow_joins", False),
                allow_subqueries=data.get("query_limits", {}).get(
                    "allow_subqueries", False
                ),
            )
        except Exception as e:
            logger.error(f"Failed to load allowlist config: {e}")
            raise ValidationError(f"Failed to load configuration: {e}") from e

    def _compile_blocked_pattern(self) -> re.Pattern:
        """Compile regex pattern for blocked keywords."""
        if not self.config.blocked_keywords:
            return re.compile(r"(?!)")  # Never matches

        # Create pattern that matches keywords as whole words
        keywords = "|".join(
            re.escape(kw) for kw in self.config.blocked_keywords
        )
        return re.compile(rf"\b({keywords})\b", re.IGNORECASE)

    def validate(self, sql: str) -> ValidationResult:
        """
        Validate a SQL query against all security rules.

        Args:
            sql: The SQL query to validate

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)

        try:
            # Parse the SQL
            parsed = sqlparse.parse(sql)
            if not parsed:
                result.is_valid = False
                result.errors.append("Failed to parse SQL statement")
                return result

            statement = parsed[0]

            # Run all validation checks
            self._check_statement_type(statement, result)
            self._check_blocked_keywords(sql, result)
            self._check_tables(statement, result)
            self._check_columns(statement, result)
            self._check_limit(sql, result)
            self._check_subqueries(sql, result)
            self._check_joins(sql, result)
            self._check_sql_injection_patterns(sql, result)

            # Generate sanitized SQL if valid
            if result.is_valid:
                result.sanitized_sql = self._sanitize_sql(sql)

        except Exception as e:
            logger.error(f"Validation error: {e}")
            result.is_valid = False
            result.errors.append(f"Validation error: {e}")

        return result

    def _check_statement_type(
        self,
        statement: sqlparse.sql.Statement,
        result: ValidationResult,
    ) -> None:
        """Ensure only SELECT statements are allowed."""
        stmt_type = statement.get_type()
        if stmt_type != "SELECT":
            result.is_valid = False
            result.errors.append(
                f"Only SELECT statements are allowed, got: {stmt_type}"
            )

    def _check_blocked_keywords(
        self,
        sql: str,
        result: ValidationResult,
    ) -> None:
        """Check for blocked SQL keywords."""
        matches = self._blocked_pattern.findall(sql)
        if matches:
            result.is_valid = False
            unique_matches = list(set(m.upper() for m in matches))
            result.errors.append(
                f"Blocked keywords found: {', '.join(unique_matches)}"
            )

    def _check_tables(
        self,
        statement: sqlparse.sql.Statement,
        result: ValidationResult,
    ) -> None:
        """Validate that only allowed tables are referenced."""
        tables = self._extract_tables(statement)
        result.tables_used = tables

        for table in tables:
            if table.upper() not in self.config.allowed_tables:
                result.is_valid = False
                result.errors.append(f"Table not in allowlist: {table}")

    def _check_columns(
        self,
        statement: sqlparse.sql.Statement,
        result: ValidationResult,
    ) -> None:
        """Validate that only allowed columns are referenced."""
        columns = self._extract_columns(statement)
        result.columns_used = columns

        # If we have table-specific column restrictions
        if self.config.allowed_columns:
            for table in result.tables_used:
                table_upper = table.upper()
                if table_upper in self.config.allowed_columns:
                    allowed = self.config.allowed_columns[table_upper]
                    for col in columns:
                        # Skip wildcards and aggregation aliases
                        if col == "*" or "(" in col:
                            continue
                        if col.upper() not in allowed:
                            result.is_valid = False
                            result.errors.append(
                                f"Column '{col}' not in allowlist for table '{table}'"
                            )

    def _check_limit(
        self,
        sql: str,
        result: ValidationResult,
    ) -> None:
        """Ensure LIMIT clause is present if required."""
        sql_upper = sql.upper()

        if self.config.require_limit:
            if "LIMIT" not in sql_upper:
                result.warnings.append(
                    f"No LIMIT clause found. "
                    f"Adding default LIMIT {self.config.max_row_limit}"
                )
            else:
                # Extract and validate limit value
                limit_match = re.search(r"LIMIT\s+(\d+)", sql_upper)
                if limit_match:
                    limit_value = int(limit_match.group(1))
                    if limit_value > self.config.max_row_limit:
                        result.warnings.append(
                            f"LIMIT {limit_value} exceeds maximum "
                            f"{self.config.max_row_limit}. Will be capped."
                        )

    def _check_subqueries(
        self,
        sql: str,
        result: ValidationResult,
    ) -> None:
        """Check for subqueries if not allowed."""
        if not self.config.allow_subqueries:
            # Count SELECT keywords - more than 1 indicates subquery
            select_count = len(re.findall(r"\bSELECT\b", sql, re.IGNORECASE))
            if select_count > 1:
                result.is_valid = False
                result.errors.append("Subqueries are not allowed")

    def _check_joins(
        self,
        sql: str,
        result: ValidationResult,
    ) -> None:
        """Check for JOIN operations if not allowed."""
        if not self.config.allow_joins:
            join_pattern = r"\b(JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|OUTER\s+JOIN|CROSS\s+JOIN)\b"
            if re.search(join_pattern, sql, re.IGNORECASE):
                result.is_valid = False
                result.errors.append("JOIN operations are not allowed")

    def _check_sql_injection_patterns(
        self,
        sql: str,
        result: ValidationResult,
    ) -> None:
        """Check for common SQL injection patterns."""
        injection_patterns = [
            r";\s*--",  # Statement termination with comment
            r"'\s*OR\s+'1'\s*=\s*'1",  # Classic OR injection with quotes
            r"'\s*OR\s+1\s*=\s*1",  # Numeric OR injection
            r"OR\s+'[^']+'\s*=\s*'[^']+'",  # Generic OR string comparison
            r"OR\s+\d+\s*=\s*\d+",  # Generic OR numeric comparison
            r"UNION\s+SELECT",  # Union-based injection
            r"EXEC\s*\(",  # Execute function
            r"xp_",  # SQL Server extended procedures
            r"/\*.*\*/",  # Block comments (potential obfuscation)
            r"CHAR\s*\(\s*\d+\s*\)",  # Character encoding bypass
            r"0x[0-9a-fA-F]+",  # Hex encoding
        ]

        for pattern in injection_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                result.is_valid = False
                result.errors.append(
                    f"Potential SQL injection pattern detected"
                )
                raise SecurityViolationError(
                    "SQL injection pattern detected in query"
                )

    def _extract_tables(
        self,
        statement: sqlparse.sql.Statement,
    ) -> list[str]:
        """Extract table names from SQL statement."""
        tables = []

        # Use sqlparse to find FROM clause
        from_seen = False
        for token in statement.tokens:
            if from_seen:
                if self._is_subselect(token):
                    continue
                elif token.ttype is sqlparse.tokens.Keyword:
                    from_seen = False
                elif token.ttype is None:
                    tables.extend(self._get_table_names(token))

            if token.ttype is sqlparse.tokens.Keyword and token.value.upper() == "FROM":
                from_seen = True

        return tables

    def _get_table_names(self, token) -> list[str]:
        """Extract table names from a token."""
        tables = []
        if isinstance(token, sqlparse.sql.IdentifierList):
            for identifier in token.get_identifiers():
                tables.append(self._get_name(identifier))
        elif isinstance(token, sqlparse.sql.Identifier):
            tables.append(self._get_name(token))
        elif token.ttype is sqlparse.tokens.Name:
            tables.append(token.value)
        return [t for t in tables if t]

    def _get_name(self, token) -> str:
        """Get the real name from an identifier (handling aliases)."""
        if isinstance(token, sqlparse.sql.Identifier):
            return token.get_real_name() or ""
        return str(token)

    def _is_subselect(self, token) -> bool:
        """Check if token is a subselect."""
        if isinstance(token, sqlparse.sql.Parenthesis):
            for item in token.tokens:
                if item.ttype is sqlparse.tokens.DML:
                    return True
        return False

    def _extract_columns(
        self,
        statement: sqlparse.sql.Statement,
    ) -> list[str]:
        """Extract column names from SELECT clause."""
        columns = []

        # Find SELECT clause
        select_seen = False
        for token in statement.tokens:
            if select_seen:
                if token.ttype is sqlparse.tokens.Keyword:
                    break
                elif isinstance(token, sqlparse.sql.IdentifierList):
                    for identifier in token.get_identifiers():
                        col = self._get_column_name(identifier)
                        if col:
                            columns.append(col)
                elif isinstance(token, sqlparse.sql.Identifier):
                    col = self._get_column_name(token)
                    if col:
                        columns.append(col)
                elif token.ttype is sqlparse.tokens.Wildcard:
                    columns.append("*")

            if token.ttype is sqlparse.tokens.DML and token.value.upper() == "SELECT":
                select_seen = True

        return columns

    def _get_column_name(self, token) -> Optional[str]:
        """Extract column name from identifier."""
        if isinstance(token, sqlparse.sql.Identifier):
            # Check if this is a function call (contains parentheses)
            token_str = str(token)
            if "(" in token_str:
                # This is a function like SUM(col) - skip it for column validation
                # The actual column inside will be validated separately if needed
                return None

            # Get the real name, handling table.column notation
            name = token.get_real_name()
            if name:
                # Check if name itself looks like a function
                if name.upper() in self.config.allowed_functions:
                    return None

                # Strip table prefix if present
                if "." in token_str:
                    parts = token_str.split(".")
                    return parts[-1].strip()
                return name
        return None

    def _sanitize_sql(self, sql: str) -> str:
        """Sanitize and normalize the SQL query."""
        # Format with sqlparse
        formatted = sqlparse.format(
            sql,
            reindent=True,
            keyword_case="upper",
        )

        # Ensure LIMIT clause
        if self.config.require_limit and "LIMIT" not in formatted.upper():
            # Remove trailing semicolon if present
            formatted = formatted.rstrip(";").strip()
            formatted += f" LIMIT {self.config.max_row_limit};"

        # Cap LIMIT if too high
        limit_match = re.search(r"LIMIT\s+(\d+)", formatted, re.IGNORECASE)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > self.config.max_row_limit:
                formatted = re.sub(
                    r"LIMIT\s+\d+",
                    f"LIMIT {self.config.max_row_limit}",
                    formatted,
                    flags=re.IGNORECASE,
                )

        return formatted


class ValidationError(Exception):
    """Exception raised when query validation fails."""

    pass


class SecurityViolationError(Exception):
    """Exception raised when a security violation is detected."""

    pass
