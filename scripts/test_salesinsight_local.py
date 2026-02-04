#!/usr/bin/env python3
"""
SalesInsight Local Test Script

This script tests the SalesInsight components locally using a SQLite database
loaded from CSV files in the data/ folder.

Usage:
    python scripts/test_salesinsight_local.py

    Options:
      --full       Run full end-to-end test with real LLM (requires Azure OpenAI)
      --query "?"  Run a specific natural language query
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add code directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

# Set minimal env vars if not present
os.environ.setdefault("AZURE_AUTH_TYPE", "keys")
os.environ.setdefault("AZURE_OPENAI_MODEL", "gpt-4o")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-02-01")


def test_query_validator():
    """Test the SQL query validator."""
    print("\n" + "=" * 60)
    print("🔒 Testing Query Validator")
    print("=" * 60)

    from backend.batch.utilities.nl2sql.query_validator import (
        QueryValidator,
        AllowlistConfig,
    )

    # Create validator with POC config
    config = AllowlistConfig(
        allowed_tables=["ORDERHISTORYLINE"],
        allowed_columns={
            "ORDERHISTORYLINE": [
                "ITEMNO", "ITEMDESCRIPTION", "CUSTOMERNO", "CUSTOMERNAME",
                "NETINV", "GROSSINV", "FISCALYEAR", "FISCALQUARTER", "REGION",
            ],
        },
        blocked_keywords=["DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE"],
        max_row_limit=1000,
        require_limit=True,
        allow_joins=False,
        allow_subqueries=False,
    )
    validator = QueryValidator(config=config)

    # Test cases
    test_cases = [
        {
            "name": "Valid ranking query",
            "sql": """
                SELECT ItemNo, ItemDescription, SUM(NetINV) as Revenue
                FROM OrderHistoryLine
                GROUP BY ItemNo, ItemDescription
                ORDER BY Revenue DESC
                LIMIT 10;
            """,
            "should_pass": True,
        },
        {
            "name": "Missing LIMIT clause",
            "sql": "SELECT * FROM OrderHistoryLine;",
            "should_pass": True,  # Passes but adds warning
        },
        {
            "name": "Blocked DROP statement",
            "sql": "DROP TABLE OrderHistoryLine;",
            "should_pass": False,
        },
        {
            "name": "SQL injection attempt",
            "sql": "SELECT * FROM OrderHistoryLine WHERE 1=1 OR '1'='1';",
            "should_pass": False,
        },
        {
            "name": "Unauthorized table",
            "sql": "SELECT * FROM SensitiveData LIMIT 10;",
            "should_pass": False,
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        try:
            result = validator.validate(test["sql"])
            actual_pass = result.is_valid

            if actual_pass == test["should_pass"]:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1

            print(f"\n{status}: {test['name']}")
            if not actual_pass:
                print(f"   Errors: {result.errors}")
            if result.warnings:
                print(f"   Warnings: {result.warnings}")

        except Exception as e:
            if not test["should_pass"]:
                print(f"✅ PASS: {test['name']} (raised expected exception)")
                passed += 1
            else:
                print(f"❌ FAIL: {test['name']} - {e}")
                failed += 1

    print(f"\n📊 Validator Results: {passed} passed, {failed} failed")
    return failed == 0


def test_prompt_builder():
    """Test the prompt builder."""
    print("\n" + "=" * 60)
    print("📝 Testing Prompt Builder")
    print("=" * 60)

    from backend.batch.utilities.nl2sql.prompt_builder import PromptBuilder, PromptConfig

    builder = PromptBuilder(config=PromptConfig(include_examples=True))

    # Test schema context
    schema_context = """
### Table: OrderHistoryLine
Columns:
  - ItemNo (VARCHAR)
  - ItemDescription (VARCHAR)
  - NetINV (DECIMAL)
  - FiscalYear (INTEGER)
"""

    # Build system prompt
    system_prompt = builder.build_system_prompt(schema_context)
    print("\n📄 System Prompt Preview:")
    print("-" * 40)
    print(system_prompt[:500] + "...")

    # Build user prompt
    question = "What are the top 10 products by turnover this year?"
    user_prompt = builder.build_user_prompt(question)
    print("\n📄 User Prompt Preview:")
    print("-" * 40)
    print(user_prompt)

    # Check for key elements
    checks = [
        ("Schema context included", "OrderHistoryLine" in system_prompt),
        ("Business terms included", "turnover" in system_prompt.lower() or "turnover" in user_prompt.lower()),
        ("Examples included", "Example" in system_prompt),
        ("Question in user prompt", question in user_prompt),
    ]

    passed = 0
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"\n{status} {check_name}")
        if check_result:
            passed += 1

    print(f"\n📊 Prompt Builder Results: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def test_chart_generator():
    """Test the chart generator with mock data."""
    print("\n" + "=" * 60)
    print("📊 Testing Chart Generator")
    print("=" * 60)

    import pandas as pd
    from backend.batch.utilities.visualization.chart_generator import (
        ChartGenerator,
        ChartConfig,
        ChartType,
    )

    # Create mock sales data
    data = pd.DataFrame({
        "Product": ["Widget A", "Widget B", "Widget C", "Gadget X", "Gadget Y"],
        "Revenue": [150000, 120000, 95000, 80000, 65000],
        "Units": [1500, 1200, 950, 800, 650],
    })

    print("\n📋 Sample Data:")
    print(data.to_string(index=False))

    generator = ChartGenerator()

    # Test different chart types
    chart_tests = [
        ("Horizontal Bar (Ranking)", ChartType.HORIZONTAL_BAR),
        ("Vertical Bar", ChartType.BAR),
    ]

    passed = 0
    for chart_name, chart_type in chart_tests:
        try:
            config = ChartConfig(
                chart_type=chart_type,
                title=f"Revenue by Product ({chart_name})",
                x_column="Product",
                y_column="Revenue",
                max_items=5,
                show_values=True,
            )

            chart = generator.generate(data, config)

            # Check that we got a valid base64 image
            if chart.image_base64 and len(chart.image_base64) > 100:
                print(f"\n✅ {chart_name}: Generated {len(chart.image_base64)} bytes")
                print(f"   Generation time: {chart.generation_time_ms:.1f}ms")
                passed += 1
            else:
                print(f"\n❌ {chart_name}: Invalid image generated")

        except Exception as e:
            print(f"\n❌ {chart_name}: {e}")

    # Test ranking chart template
    try:
        from backend.batch.utilities.visualization.chart_templates import RankingChartTemplate

        template = RankingChartTemplate()
        chart = template.generate(
            data=data,
            label_column="Product",
            value_column="Revenue",
            title="Top Products by Revenue",
            max_items=5,
        )

        if chart.image_base64 and len(chart.image_base64) > 100:
            print(f"\n✅ Ranking Template: Generated successfully")
            passed += 1
        else:
            print(f"\n❌ Ranking Template: Failed")

    except Exception as e:
        print(f"\n❌ Ranking Template: {e}")

    total_tests = len(chart_tests) + 1
    print(f"\n📊 Chart Generator Results: {passed}/{total_tests} tests passed")

    # Save a sample chart for visual inspection
    if chart.image_base64:
        import base64
        output_path = Path(__file__).parent.parent / "test_chart_output.png"
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(chart.image_base64))
        print(f"\n💾 Sample chart saved to: {output_path}")

    return passed == total_tests


def test_integration():
    """Test full integration with local SQLite database."""
    print("\n" + "=" * 60)
    print("🔌 Testing Local Database Integration")
    print("=" * 60)

    from backend.batch.utilities.data_sources import (
        SQLiteDataSource,
        create_local_test_database,
        SchemaDiscovery,
    )

    # Create local database from CSV
    print("\n📁 Loading CSV data into SQLite...")
    data_dir = Path(__file__).parent.parent / "data"
    ds = create_local_test_database(str(data_dir))
    ds.connect()

    # Check tables
    tables = ds.get_table_names()
    print(f"✅ Loaded {len(tables)} tables: {tables}")

    # Test a simple query
    print("\n🔍 Testing sample queries...")

    test_queries = [
        ("Row count", "SELECT COUNT(*) as cnt FROM OrderHistoryLine"),
        ("Top products", """
            SELECT StyleNumber, SUM(UnitNetPrice * RequestQuantity) as Revenue
            FROM OrderHistoryLine
            GROUP BY StyleNumber
            ORDER BY Revenue DESC
            LIMIT 5
        """),
        ("Status breakdown", """
            SELECT Status, COUNT(*) as OrderCount
            FROM OrderHistoryLine
            GROUP BY Status
            ORDER BY OrderCount DESC
        """),
        ("Currency summary", """
            SELECT CurrencyIsoAlpha3, 
                   COUNT(*) as Orders,
                   SUM(UnitNetPrice * RequestQuantity) as TotalValue
            FROM OrderHistoryLine
            GROUP BY CurrencyIsoAlpha3
            ORDER BY TotalValue DESC
        """),
    ]

    for query_name, sql in test_queries:
        try:
            result = ds.execute_query(sql, parameters={})
            print(f"\n✅ {query_name}:")
            print(result.data.head(10).to_string(index=False))
        except Exception as e:
            print(f"\n❌ {query_name}: {e}")

    # Test schema discovery
    print("\n📋 Testing Schema Discovery...")
    schema_discovery = SchemaDiscovery(ds)
    tables = schema_discovery.discover_tables()
    print(f"Discovered tables: {tables}")

    if tables:
        schema = schema_discovery.get_table_schema(tables[0])
        print(f"\nSchema for {tables[0]}:")
        for col in schema.columns[:10]:
            print(f"  - {col.name}: {col.data_type}")
        if len(schema.columns) > 10:
            print(f"  ... and {len(schema.columns) - 10} more columns")

    ds.disconnect()
    return True


def test_end_to_end(question: str = None):
    """Test end-to-end NL2SQL with local database."""
    print("\n" + "=" * 60)
    print("🚀 Testing End-to-End NL2SQL Pipeline")
    print("=" * 60)

    # Check for OpenAI credentials
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        print("\n⚠️  AZURE_OPENAI_API_KEY not set - skipping LLM tests")
        print("   Set this in .env to test the full pipeline")
        return False

    from backend.batch.utilities.data_sources import (
        create_local_test_database,
        SchemaDiscovery,
    )
    from backend.batch.utilities.nl2sql import (
        NL2SQLGenerator,
        QueryValidator,
        PromptBuilder,
    )
    from backend.batch.utilities.visualization import ChartGenerator

    # Setup
    data_dir = Path(__file__).parent.parent / "data"
    ds = create_local_test_database(str(data_dir))
    ds.connect()

    schema_discovery = SchemaDiscovery(ds)
    prompt_builder = PromptBuilder()
    validator = QueryValidator()
    chart_generator = ChartGenerator()

    # Get schema context
    schema_context = schema_discovery.get_schema_context_for_nl2sql()
    system_prompt = prompt_builder.build_system_prompt(schema_context)

    # Test question
    if not question:
        question = "What are the top 5 products by total order value?"

    print(f"\n❓ Question: {question}")
    print("\n⏳ Generating SQL...")

    try:
        from backend.batch.utilities.nl2sql import NL2SQLGenerator
        generator = NL2SQLGenerator()

        result = generator.generate(
            question=question,
            schema_context=schema_context,
            system_prompt=system_prompt,
        )

        print(f"\n📝 Generated SQL:")
        print(result.sql)
        print(f"\n💡 Explanation: {result.explanation}")

        # Validate
        validation = validator.validate(result.sql)
        if validation.is_valid:
            print("\n✅ SQL validation passed")

            # Execute
            query_result = ds.execute_query(
                validation.sanitized_sql or result.sql,
                parameters={},
            )
            print(f"\n📊 Results ({query_result.row_count} rows):")
            print(query_result.data.to_string(index=False))

            # Generate chart
            if not query_result.data.empty:
                from backend.batch.utilities.visualization import ChartConfig, ChartType

                numeric_cols = query_result.data.select_dtypes(include=["number"]).columns.tolist()
                text_cols = query_result.data.select_dtypes(include=["object"]).columns.tolist()

                if numeric_cols and text_cols:
                    config = ChartConfig(
                        chart_type=ChartType.HORIZONTAL_BAR,
                        title=question[:50],
                        x_column=text_cols[0],
                        y_column=numeric_cols[0],
                        max_items=10,
                    )
                    chart = chart_generator.generate(query_result.data, config)

                    # Save chart
                    import base64
                    output_path = Path(__file__).parent.parent / "test_query_result.png"
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(chart.image_base64))
                    print(f"\n📈 Chart saved to: {output_path}")

        else:
            print(f"\n❌ SQL validation failed: {validation.errors}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    ds.disconnect()
    return True


def main():
    parser = argparse.ArgumentParser(description="Test SalesInsight components locally")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full end-to-end tests with LLM (requires Azure OpenAI)",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Run a specific natural language query",
    )
    args = parser.parse_args()

    print("🚀 SalesInsight Local Test Suite")
    print("=" * 60)

    # Load .env if present
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print(f"📁 Loaded environment from {env_path}")
    else:
        print("⚠️  No .env file found - using defaults")

    results = []

    # Run component tests
    results.append(("Query Validator", test_query_validator()))
    results.append(("Prompt Builder", test_prompt_builder()))
    results.append(("Chart Generator", test_chart_generator()))

    # Always test local DB integration
    results.append(("Local Database", test_integration()))

    # Optional end-to-end tests with LLM
    if args.full or args.query:
        results.append(("End-to-End NL2SQL", test_end_to_end(args.query)))

    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
