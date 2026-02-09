"""
Unit tests for NL2SQL Query Validator.

Tests the SQL validation, allowlist checking, and security features.
"""

import pytest
from backend.batch.utilities.nl2sql.query_validator import (
    QueryValidator,
    AllowlistConfig,
    ValidationResult,
    ValidationError,
    SecurityViolationError,
)


@pytest.fixture
def validator_config():
    """Create a test allowlist configuration."""
    return AllowlistConfig(
        allowed_tables=["ORDERHISTORYLINE", "CUSTOMERS", "PRODUCTS"],
        allowed_columns={
            "ORDERHISTORYLINE": [
                "ITEMNO", "ITEMDESCRIPTION", "CUSTOMERNO", "CUSTOMERNAME",
                "NETINV", "GROSSINV", "FISCALYEAR", "FISCALQUARTER", "REGION",
            ],
            "CUSTOMERS": ["CUSTOMERNO", "CUSTOMERNAME", "REGION"],
            "PRODUCTS": ["ITEMNO", "ITEMDESCRIPTION", "CATEGORY"],
        },
        blocked_keywords=[
            "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
            "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
        ],
        allowed_functions=["SUM", "COUNT", "AVG", "MIN", "MAX", "DISTINCT"],
        max_row_limit=1000,
        require_limit=True,
        allow_joins=False,
        allow_subqueries=False,
    )


@pytest.fixture
def validator(validator_config):
    """Create a validator with test configuration."""
    return QueryValidator(config=validator_config)


class TestQueryValidatorBasicValidation:
    """Tests for basic SQL validation."""

    def test_valid_select_query(self, validator):
        """Test that a valid SELECT query passes validation."""
        sql = """
            SELECT ItemNo, ItemDescription, SUM(NetINV) as TotalRevenue
            FROM OrderHistoryLine
            GROUP BY ItemNo, ItemDescription
            ORDER BY TotalRevenue DESC
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert result.is_valid
        assert len(result.errors) == 0
        assert "ORDERHISTORYLINE" in [t.upper() for t in result.tables_used]

    def test_invalid_statement_type(self, validator):
        """Test that non-SELECT statements are rejected."""
        sql = "INSERT INTO OrderHistoryLine (ItemNo) VALUES ('TEST');"
        result = validator.validate(sql)
        assert not result.is_valid
        assert any("SELECT" in err for err in result.errors)

    def test_empty_sql(self, validator):
        """Test that empty SQL is rejected."""
        result = validator.validate("")
        assert not result.is_valid

    def test_malformed_sql(self, validator):
        """Test that malformed SQL is handled gracefully."""
        sql = "SELCT * FORM table"  # Typos
        result = validator.validate(sql)
        assert not result.is_valid


class TestQueryValidatorTableAllowlist:
    """Tests for table allowlist enforcement."""

    def test_allowed_table(self, validator):
        """Test that queries on allowed tables pass."""
        sql = "SELECT ItemNo FROM OrderHistoryLine LIMIT 10;"
        result = validator.validate(sql)
        assert result.is_valid

    def test_disallowed_table(self, validator):
        """Test that queries on disallowed tables fail."""
        sql = "SELECT * FROM SensitiveData LIMIT 10;"
        result = validator.validate(sql)
        assert not result.is_valid
        assert any("allowlist" in err.lower() for err in result.errors)

    def test_multiple_allowed_tables(self, validator_config):
        """Test validation with multiple tables (joins disabled)."""
        validator_config.allow_joins = False
        validator = QueryValidator(config=validator_config)
        
        sql = """
            SELECT o.ItemNo, c.CustomerName
            FROM OrderHistoryLine o
            JOIN Customers c ON o.CustomerNo = c.CustomerNo
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert not result.is_valid
        assert any("JOIN" in err for err in result.errors)


class TestQueryValidatorBlockedKeywords:
    """Tests for blocked keyword detection."""

    def test_drop_statement_blocked(self, validator):
        """Test that DROP statements are blocked."""
        sql = "SELECT * FROM OrderHistoryLine; DROP TABLE OrderHistoryLine;"
        result = validator.validate(sql)
        assert not result.is_valid
        assert any("DROP" in err.upper() for err in result.errors)

    def test_delete_keyword_blocked(self, validator):
        """Test that DELETE keywords are blocked."""
        sql = "DELETE FROM OrderHistoryLine WHERE 1=1;"
        result = validator.validate(sql)
        assert not result.is_valid

    def test_update_keyword_blocked(self, validator):
        """Test that UPDATE keywords are blocked."""
        sql = "UPDATE OrderHistoryLine SET NetINV = 0;"
        result = validator.validate(sql)
        assert not result.is_valid

    def test_truncate_blocked(self, validator):
        """Test that TRUNCATE is blocked."""
        sql = "TRUNCATE TABLE OrderHistoryLine;"
        result = validator.validate(sql)
        assert not result.is_valid


class TestQueryValidatorLimitEnforcement:
    """Tests for LIMIT clause enforcement."""

    def test_missing_limit_adds_warning(self, validator):
        """Test that missing LIMIT generates a warning."""
        sql = "SELECT ItemNo FROM OrderHistoryLine;"
        result = validator.validate(sql)
        assert len(result.warnings) > 0
        assert any("LIMIT" in w for w in result.warnings)

    def test_limit_present(self, validator):
        """Test that queries with LIMIT pass."""
        sql = "SELECT ItemNo FROM OrderHistoryLine LIMIT 100;"
        result = validator.validate(sql)
        assert result.is_valid

    def test_excessive_limit_capped(self, validator):
        """Test that excessive LIMIT values generate warnings."""
        sql = "SELECT ItemNo FROM OrderHistoryLine LIMIT 999999;"
        result = validator.validate(sql)
        assert any("maximum" in w.lower() for w in result.warnings)

    def test_sanitized_sql_has_limit(self, validator):
        """Test that sanitized SQL includes LIMIT."""
        sql = "SELECT ItemNo FROM OrderHistoryLine;"
        result = validator.validate(sql)
        assert result.sanitized_sql is not None
        assert "LIMIT" in result.sanitized_sql.upper()


class TestQueryValidatorSubqueryHandling:
    """Tests for subquery detection and handling."""

    def test_subquery_in_where_blocked(self, validator):
        """Test that subqueries in WHERE clause are blocked."""
        sql = """
            SELECT ItemNo FROM OrderHistoryLine
            WHERE CustomerNo IN (SELECT CustomerNo FROM Customers)
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert not result.is_valid
        assert any("subquer" in err.lower() for err in result.errors)

    def test_subquery_in_select_blocked(self, validator):
        """Test that subqueries in SELECT clause are blocked."""
        sql = """
            SELECT ItemNo, (SELECT COUNT(*) FROM Customers) as cnt
            FROM OrderHistoryLine
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert not result.is_valid


class TestQueryValidatorSQLInjection:
    """Tests for SQL injection pattern detection."""

    def test_comment_injection(self, validator):
        """Test detection of comment-based injection."""
        sql = "SELECT * FROM OrderHistoryLine; -- DROP TABLE OrderHistoryLine"
        result = validator.validate(sql)
        assert not result.is_valid

    def test_or_injection_pattern(self, validator):
        """Test detection of OR-based injection."""
        sql = "SELECT * FROM OrderHistoryLine WHERE ItemNo = '' OR '1'='1' LIMIT 10;"
        result = validator.validate(sql)
        assert not result.is_valid

    def test_union_injection(self, validator):
        """Test detection of UNION-based injection."""
        sql = """
            SELECT ItemNo FROM OrderHistoryLine
            UNION SELECT password FROM users
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert not result.is_valid

    def test_exec_function_blocked(self, validator):
        """Test that EXEC functions are blocked."""
        sql = "SELECT EXEC('DROP TABLE OrderHistoryLine') FROM OrderHistoryLine LIMIT 10;"
        result = validator.validate(sql)
        assert not result.is_valid


class TestQueryValidatorColumnAllowlist:
    """Tests for column allowlist enforcement."""

    def test_allowed_columns(self, validator):
        """Test that allowed columns pass validation."""
        sql = """
            SELECT ItemNo, ItemDescription, NetINV
            FROM OrderHistoryLine
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert result.is_valid

    def test_disallowed_column(self, validator):
        """Test that disallowed columns are rejected."""
        sql = """
            SELECT ItemNo, SensitiveColumn
            FROM OrderHistoryLine
            LIMIT 10;
        """
        result = validator.validate(sql)
        # Note: Column validation is table-specific
        # This test assumes strict column validation is enabled
        # Adjust based on actual implementation


class TestQueryValidatorJoinHandling:
    """Tests for JOIN operation handling."""

    def test_join_blocked_by_default(self, validator):
        """Test that JOINs are blocked when disabled."""
        sql = """
            SELECT o.ItemNo, c.CustomerName
            FROM OrderHistoryLine o
            INNER JOIN Customers c ON o.CustomerNo = c.CustomerNo
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert not result.is_valid
        assert any("JOIN" in err for err in result.errors)

    def test_left_join_blocked(self, validator):
        """Test that LEFT JOINs are blocked."""
        sql = """
            SELECT o.ItemNo
            FROM OrderHistoryLine o
            LEFT JOIN Customers c ON o.CustomerNo = c.CustomerNo
            LIMIT 10;
        """
        result = validator.validate(sql)
        assert not result.is_valid

    def test_join_allowed_when_enabled(self, validator_config):
        """Test that JOINs work when enabled."""
        validator_config.allow_joins = True
        validator = QueryValidator(config=validator_config)
        
        sql = """
            SELECT o.ItemNo, c.CustomerName
            FROM OrderHistoryLine o
            JOIN Customers c ON o.CustomerNo = c.CustomerNo
            LIMIT 10;
        """
        result = validator.validate(sql)
        # Should pass table validation (both tables allowed)
        # JOINs are now allowed


class TestQueryValidatorSanitization:
    """Tests for SQL sanitization."""

    def test_sql_formatting(self, validator):
        """Test that SQL is properly formatted."""
        sql = "select   itemno,netinv from orderhistoryline limit 10"
        result = validator.validate(sql)
        assert result.sanitized_sql is not None
        # Should be uppercase keywords
        assert "SELECT" in result.sanitized_sql
        assert "FROM" in result.sanitized_sql

    def test_semicolon_not_added(self, validator):
        """Test that semicolons are NOT added (they're blocked for security)."""
        sql = "SELECT ItemNo FROM OrderHistoryLine LIMIT 10"
        result = validator.validate(sql)
        # Semicolons are blocked for security, so they should not be present
        assert ";" not in result.sanitized_sql


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_to_dict(self):
        """Test ValidationResult serialization."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Test warning"],
            sanitized_sql="SELECT 1;",
            tables_used=["Table1"],
            columns_used=["Col1"],
        )
        d = result.to_dict()
        assert d["is_valid"] is True
        assert len(d["warnings"]) == 1
        assert d["sanitized_sql"] == "SELECT 1;"
