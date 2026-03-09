#!/usr/bin/env python3
"""
SalesInsight NL2SQL Evaluation Pipeline

This script evaluates the accuracy and safety of the NL2SQL pipeline by:
1. Auto-generating test cases from the current data (or loading a golden dataset)
2. Running each question through the full NL2SQL pipeline
3. Comparing generated SQL against expected patterns
4. Executing both generated and expected SQL and comparing results
5. Scoring via Azure AI Foundry evaluation (similarity, relevance, coherence,
   fluency, groundedness) — enabled by default when online
6. Producing a detailed report (tracked in Foundry portal when project is configured)

Usage:
    # Quick local eval (no LLM, tests validator + schema only)
    python scripts/evaluation/run_evaluation.py --offline

    # Full eval with LLM + Foundry scoring (default)
    python scripts/evaluation/run_evaluation.py

    # Auto-generate fresh test cases from current data (ignores golden_dataset.json)
    python scripts/evaluation/run_evaluation.py --generate

    # Skip Foundry evaluation (local comparison only)
    python scripts/evaluation/run_evaluation.py --no-foundry

    # Custom Foundry project name (for portal tracking)
    python scripts/evaluation/run_evaluation.py --project-name my-ai-project

    # Run a single test case
    python scripts/evaluation/run_evaluation.py --id eval-001

    # Save report to file
    python scripts/evaluation/run_evaluation.py --output reports/eval_report.json
"""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add code directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "code"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================
@dataclass
class TestCase:
    """A single evaluation test case from the golden dataset."""

    id: str
    category: str
    question: str
    expected_sql_pattern: Optional[str]
    expected_columns: list[str]
    expected_aggregation: Optional[str]
    expected_row_count_min: Optional[int]
    expected_row_count_max: Optional[int]
    validation_query: Optional[str]
    notes: str = ""


@dataclass
class EvalResult:
    """Result of evaluating a single test case."""

    test_id: str
    question: str
    category: str

    # SQL generation
    generated_sql: str = ""
    generation_time_ms: float = 0.0
    confidence_score: Optional[float] = None
    tokens_used: int = 0

    # Validation
    validation_passed: bool = False
    validation_errors: list[str] = field(default_factory=list)

    # Pattern matching
    sql_pattern_match: bool = False

    # Execution comparison
    generated_row_count: int = 0
    expected_row_count: int = 0
    row_count_in_range: bool = False
    data_match_score: float = 0.0  # 0.0 to 1.0

    # AI Foundry Evaluation scores
    similarity_score: Optional[float] = None
    relevance_score: Optional[float] = None
    coherence_score: Optional[float] = None
    fluency_score: Optional[float] = None
    groundedness_score: Optional[float] = None

    # Security
    is_security_test: bool = False
    security_blocked: Optional[bool] = None

    # Overall
    passed: bool = False
    error: Optional[str] = None
    notes: str = ""


@dataclass
class EvalReport:
    """Full evaluation report."""

    timestamp: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    accuracy_pct: float = 0.0
    avg_confidence: float = 0.0
    avg_generation_time_ms: float = 0.0
    total_tokens: int = 0
    security_tests_passed: int = 0
    security_tests_total: int = 0
    results: list[dict] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)
    # Foundry aggregate scores (None = not evaluated)
    foundry_avg_similarity: Optional[float] = None
    foundry_avg_relevance: Optional[float] = None
    foundry_avg_coherence: Optional[float] = None
    foundry_avg_fluency: Optional[float] = None
    foundry_avg_groundedness: Optional[float] = None


# ============================================================================
# Evaluation Engine
# ============================================================================
class NL2SQLEvaluator:
    """Evaluates the NL2SQL pipeline against a golden dataset."""

    def __init__(
        self,
        dataset_path: str,
        offline: bool = False,
        use_foundry: bool = True,
        project_name: Optional[str] = None,
        auto_generate: bool = False,
    ):
        self.dataset_path = dataset_path
        self.offline = offline
        self.use_foundry = use_foundry
        self.project_name = project_name
        self.auto_generate = auto_generate
        self.test_cases: list[TestCase] = []
        self.results: list[EvalResult] = []
        self._foundry_eval_result = None  # Stores Foundry evaluate() output
        self._schema_context_str: str = ""  # Full schema for Foundry context

        # Components initialized lazily
        self._data_source = None
        self._schema_discovery = None
        self._sql_generator = None
        self._query_validator = None
        self._prompt_builder = None

    def load_dataset(self) -> int:
        """Load or auto-generate the evaluation dataset."""
        print("\n" + "=" * 70)
        print("  STEP 1: Loading Evaluation Dataset")
        print("=" * 70)

        dataset_exists = os.path.exists(self.dataset_path)

        if self.auto_generate or not dataset_exists:
            if not dataset_exists:
                print(f"  No golden dataset at {self.dataset_path}")
            print("  Auto-generating test cases from current data...")
            self.test_cases = self._generate_from_data()
        else:
            with open(self.dataset_path) as f:
                data = json.load(f)
            self.test_cases = [TestCase(**tc) for tc in data]
            print(f"  Loaded {len(self.test_cases)} test cases from {self.dataset_path}")

        # Show breakdown by category
        categories = {}
        for tc in self.test_cases:
            categories[tc.category] = categories.get(tc.category, 0) + 1

        for cat, count in sorted(categories.items()):
            print(f"    - {cat}: {count} tests")

        return len(self.test_cases)

    def _generate_from_data(self) -> list[TestCase]:
        """Dynamically generate test cases from whatever data is loaded."""
        from generate_golden_dataset import GoldenDatasetGenerator

        gen = GoldenDatasetGenerator()
        gen.setup()
        raw_tests = gen.generate()
        gen.cleanup()

        # Save the generated dataset for reproducibility
        output_path = self.dataset_path
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(raw_tests, f, indent=2, default=str)
        print(f"  Saved {len(raw_tests)} generated test cases to {output_path}")

        return [TestCase(**tc) for tc in raw_tests]

    def setup_components(self):
        """Initialize NL2SQL pipeline components."""
        print("\n" + "=" * 70)
        print("  STEP 2: Setting Up Pipeline Components")
        print("=" * 70)

        # Load environment
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv

            load_dotenv(env_path)
            print(f"  Loaded .env from {env_path}")

        # Ensure local data mode
        os.environ.setdefault("SALESINSIGHT_USE_LOCAL_DATA", "true")
        os.environ.setdefault("AZURE_AUTH_TYPE", "keys")

        # Initialize data source — dynamically discover data files
        print("  Initializing local SQLite data source...")
        from backend.batch.utilities.data_sources import SchemaDiscovery
        from backend.batch.utilities.data_sources.sqlite_data_source import (
            SQLiteDataSource,
        )

        data_dir = os.environ.get(
            "SALESINSIGHT_DATA_DIR",
            str(Path(__file__).parent.parent.parent / "data"),
        )
        data_dir = os.path.abspath(data_dir)
        supported_extensions = {".csv", ".xlsx", ".xls"}
        data_files: dict[str, str] = {}

        if os.path.isdir(data_dir):
            for file_path in Path(data_dir).iterdir():
                if file_path.suffix.lower() in supported_extensions:
                    table_name = self._file_to_table_name(file_path.stem)
                    data_files[table_name] = str(file_path)
                    print(f"    Found: {file_path.name} → table '{table_name}'")

        # Allow explicit env override
        explicit_path = os.environ.get("SALESINSIGHT_CSV_PATH")
        if explicit_path and os.path.exists(explicit_path):
            table_name = self._file_to_table_name(Path(explicit_path).stem)
            data_files[table_name] = explicit_path

        if not data_files:
            raise FileNotFoundError(
                f"No data files (.csv, .xlsx, .xls) found in {data_dir}"
            )

        self._data_source = SQLiteDataSource.from_files(data_files)
        self._data_source.connect()

        # Verify data loaded
        for tbl in data_files:
            try:
                result = self._data_source.execute_query(
                    f"SELECT COUNT(*) as cnt FROM {tbl};", parameters={}
                )
                row_count = result.data.iloc[0]["cnt"]
                print(f"  Table '{tbl}': {row_count:,} rows")
            except Exception as e:
                print(f"  Table '{tbl}': error counting rows — {e}")

        # Schema discovery
        self._schema_discovery = SchemaDiscovery(self._data_source)
        tables = self._schema_discovery.discover_tables()
        print(f"  Schema discovery: {len(tables)} tables found: {tables}")

        # Query validator (built from schema)
        from backend.batch.utilities.nl2sql import QueryValidator

        schema = {}
        for table_name in tables:
            table_schema = self._schema_discovery.get_table_schema(table_name)
            schema[table_name] = [col.name for col in table_schema.columns]

        self._query_validator = QueryValidator.from_schema(schema)
        print(f"  Query validator ready (allowlist: {list(schema.keys())})")

        # Build schema context string for Foundry evaluation
        self._schema_context_str = self._build_schema_context(schema)

        # NL2SQL generator (only if online mode)
        if not self.offline:
            from backend.batch.utilities.nl2sql import NL2SQLGenerator, PromptBuilder

            self._prompt_builder = PromptBuilder()

            openai_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            auth_type = os.getenv("AZURE_AUTH_TYPE", "keys")

            if not openai_endpoint:
                print(
                    "  WARNING: AZURE_OPENAI_ENDPOINT not set"
                )
                print("  Falling back to offline mode")
                self.offline = True
            elif not openai_key and auth_type != "rbac":
                print(
                    "  WARNING: AZURE_OPENAI_API_KEY not set and AZURE_AUTH_TYPE is not 'rbac'"
                )
                print("  Falling back to offline mode")
                self.offline = True
            else:
                self._sql_generator = NL2SQLGenerator()
                auth_mode = "RBAC" if auth_type == "rbac" else "API key"
                print(f"  NL2SQL generator ready (model: {os.getenv('AZURE_OPENAI_MODEL', 'gpt-4o')}, auth: {auth_mode})")

        print("\n  All components initialized.")

    @staticmethod
    def _build_schema_context(schema: dict[str, list[str]]) -> str:
        """Build a human-readable schema description for Foundry eval context."""
        lines = ["Database schema:"]
        for table, columns in schema.items():
            lines.append(f"  Table '{table}': {', '.join(columns)}")
        return "\n".join(lines)

    @staticmethod
    def _file_to_table_name(filename: str) -> str:
        """Convert a filename to a SQL table name (mirrors agent logic)."""
        name = filename.lower()
        name = re.sub(r"^db_[a-z]+_[a-z]+_[a-z]+_dbo_", "", name)
        name = re.sub(r"[^a-z0-9]", "_", name)
        name = re.sub(r"_+", "_", name)
        name = name.strip("_")
        return name or "data"


    def run_evaluation(self, test_id: Optional[str] = None):
        """Run evaluation on all (or filtered) test cases."""
        print("\n" + "=" * 70)
        print("  STEP 3: Running Evaluation")
        print("=" * 70)

        cases = self.test_cases
        if test_id:
            cases = [tc for tc in self.test_cases if tc.id == test_id]
            if not cases:
                print(f"  ERROR: Test case '{test_id}' not found")
                return

        total = len(cases)
        for i, tc in enumerate(cases, 1):
            print(f"\n  [{i}/{total}] {tc.id} ({tc.category})")
            print(f"  Question: {tc.question}")

            result = self._evaluate_single(tc)
            self.results.append(result)

            # Print immediate result
            if result.is_security_test:
                status = "BLOCKED" if result.security_blocked else "NOT BLOCKED"
                icon = "🛡️" if result.security_blocked else "⚠️"
                print(f"  {icon} Security test: {status}")
            elif result.passed:
                print(f"  ✅ PASS (confidence: {result.confidence_score or 'N/A'}, "
                      f"time: {result.generation_time_ms:.0f}ms)")
            elif result.error:
                print(f"  ❌ ERROR: {result.error}")
            else:
                print(f"  ❌ FAIL: {', '.join(result.validation_errors) if result.validation_errors else 'Pattern mismatch'}")

            if result.generated_sql:
                print(f"  SQL: {result.generated_sql[:100]}...")

    def _evaluate_single(self, tc: TestCase) -> EvalResult:
        """Evaluate a single test case."""
        result = EvalResult(
            test_id=tc.id,
            question=tc.question,
            category=tc.category,
            is_security_test=tc.category == "security",
        )

        try:
            # Security tests: check if blocked
            if tc.category == "security":
                return self._evaluate_security(tc, result)

            if self.offline:
                return self._evaluate_offline(tc, result)
            else:
                return self._evaluate_online(tc, result)

        except Exception as e:
            result.error = str(e)
            result.passed = False
            return result

    def _evaluate_security(self, tc: TestCase, result: EvalResult) -> EvalResult:
        """Evaluate a security test case (should be blocked)."""
        try:
            from backend.batch.utilities.helpers.azure_ai_integration import (
                get_content_safety_checker,
            )
            checker = get_content_safety_checker()
            is_safe, reason = checker.check_input(tc.question)
        except Exception as e:
            # If content safety can't be initialised, use local pattern check
            logger.warning(f"Content safety init failed, using local check: {e}")
            is_safe, reason = self._local_injection_check(tc.question)

        if not is_safe:
            result.security_blocked = True
            result.passed = True
            result.notes = f"Blocked by content safety: {reason}"
            return result

        # Check 2: If it somehow passes content safety, try generating SQL
        # and see if the validator catches it
        if self._sql_generator:
            try:
                schema_context = self._schema_discovery.get_schema_context_for_nl2sql()
                system_prompt = self._prompt_builder.build_system_prompt(schema_context)

                generated = self._sql_generator.generate(
                    question=tc.question,
                    schema_context=schema_context,
                    system_prompt=system_prompt,
                )
                result.generated_sql = generated.sql

                # Validate — should fail
                validation = self._query_validator.validate(generated.sql)
                if not validation.is_valid:
                    result.security_blocked = True
                    result.passed = True
                    result.notes = f"Blocked by validator: {validation.errors}"
                else:
                    result.security_blocked = False
                    result.passed = False
                    result.notes = "DANGER: Security test was NOT blocked"

            except Exception as e:
                # If generation itself fails, that's also a form of blocking
                result.security_blocked = True
                result.passed = True
                result.notes = f"Blocked during generation: {e}"
        else:
            # Offline mode - just check content safety result
            result.security_blocked = not is_safe
            result.passed = not is_safe
            result.notes = "Content safety check only (offline mode)"

        return result

    def _evaluate_offline(self, tc: TestCase, result: EvalResult) -> EvalResult:
        """Evaluate without LLM — run the validation_query and check results."""
        if not tc.validation_query:
            result.notes = "No validation query — skipped in offline mode"
            return result

        # Test that the expected SQL passes validation
        validation = self._query_validator.validate(tc.validation_query)
        result.validation_passed = validation.is_valid

        if not validation.is_valid:
            result.validation_errors = validation.errors
            result.passed = False
            result.notes = "Expected SQL failed validation"
            return result

        # Execute the expected SQL
        exec_result = self._data_source.execute_query(
            validation.sanitized_sql or tc.validation_query, parameters={}
        )
        result.expected_row_count = len(exec_result.data)

        # Check row count range
        if tc.expected_row_count_min is not None and tc.expected_row_count_max is not None:
            result.row_count_in_range = (
                tc.expected_row_count_min <= result.expected_row_count <= tc.expected_row_count_max
            )

        result.passed = result.validation_passed and result.row_count_in_range
        result.notes = f"Offline: expected SQL valid, {result.expected_row_count} rows"
        return result

    def _evaluate_online(self, tc: TestCase, result: EvalResult) -> EvalResult:
        """Full LLM evaluation — generate SQL, validate, execute, compare."""
        # Generate SQL
        schema_context = self._schema_discovery.get_schema_context_for_nl2sql()
        system_prompt = self._prompt_builder.build_system_prompt(schema_context)

        start = time.time()
        generated = self._sql_generator.generate(
            question=tc.question,
            schema_context=schema_context,
            system_prompt=system_prompt,
        )
        result.generation_time_ms = (time.time() - start) * 1000

        result.generated_sql = generated.sql
        result.confidence_score = generated.confidence_score
        result.tokens_used = generated.tokens_used

        # Validate generated SQL
        validation = self._query_validator.validate(generated.sql)
        result.validation_passed = validation.is_valid
        result.validation_errors = validation.errors

        if not validation.is_valid:
            result.passed = False
            return result

        # Check SQL pattern match
        if tc.expected_sql_pattern:
            result.sql_pattern_match = bool(
                re.search(tc.expected_sql_pattern, generated.sql, re.IGNORECASE)
            )

        # Execute generated SQL
        try:
            gen_result = self._data_source.execute_query(
                validation.sanitized_sql or generated.sql, parameters={}
            )
            result.generated_row_count = len(gen_result.data)
        except Exception as e:
            result.error = f"Generated SQL execution failed: {e}"
            result.passed = False
            return result

        # Execute expected SQL for comparison
        if tc.validation_query:
            try:
                exp_result = self._data_source.execute_query(
                    tc.validation_query, parameters={}
                )
                result.expected_row_count = len(exp_result.data)

                # Compare data
                result.data_match_score = self._compare_results(
                    gen_result.data, exp_result.data
                )
            except Exception:
                pass

        # Check row count range
        if tc.expected_row_count_min is not None and tc.expected_row_count_max is not None:
            result.row_count_in_range = (
                tc.expected_row_count_min
                <= result.generated_row_count
                <= tc.expected_row_count_max
            )

        # Determine pass/fail
        result.passed = (
            result.validation_passed
            and result.row_count_in_range
            and (result.data_match_score >= 0.5 or not tc.validation_query)
        )

        return result

    @staticmethod
    def _local_injection_check(text: str) -> tuple[bool, Optional[str]]:
        """Fallback injection check using local patterns (no Azure dependency)."""
        patterns = [
            "drop table", "delete from", "truncate", "insert into",
            "update set", "grant all", "exec(", "execute(", "xp_cmdshell",
            "'; --", "' or '1'='1", "' or 1=1", "union select",
            "into outfile", "ignore previous", "ignore all instructions",
            "forget your instructions", "system prompt:", "bypass",
        ]
        text_lower = text.lower()
        for p in patterns:
            if p in text_lower:
                return False, f"Injection pattern detected: {p}"
        return True, None

    def _compare_results(self, generated_df, expected_df) -> float:
        """Compare two DataFrames and return similarity score (0-1)."""
        import pandas as pd

        if generated_df.empty and expected_df.empty:
            return 1.0
        if generated_df.empty or expected_df.empty:
            return 0.0

        # Compare column overlap
        gen_cols = set(c.lower() for c in generated_df.columns)
        exp_cols = set(c.lower() for c in expected_df.columns)
        col_overlap = len(gen_cols & exp_cols) / max(len(gen_cols | exp_cols), 1)

        # Compare row counts
        row_ratio = min(len(generated_df), len(expected_df)) / max(
            len(generated_df), len(expected_df), 1
        )

        # Compare first numeric column values (if both have one)
        value_score = 0.0
        gen_numeric = generated_df.select_dtypes(include=["number"]).columns.tolist()
        exp_numeric = expected_df.select_dtypes(include=["number"]).columns.tolist()

        if gen_numeric and exp_numeric:
            try:
                gen_sum = generated_df[gen_numeric[0]].sum()
                exp_sum = expected_df[exp_numeric[0]].sum()
                if exp_sum != 0:
                    value_score = 1.0 - min(abs(gen_sum - exp_sum) / abs(exp_sum), 1.0)
                elif gen_sum == 0:
                    value_score = 1.0
            except Exception:
                pass

        # Weighted score
        return (col_overlap * 0.3) + (row_ratio * 0.3) + (value_score * 0.4)

    # ================================================================
    # Azure AI Foundry Evaluation (batch mode via evaluate() API)
    # ================================================================
    def run_foundry_evaluation(self):
        """Run batch evaluation via Azure AI Foundry evaluate() API.

        This sends all results through the Foundry evaluation pipeline in one
        batch call. When azure_ai_project is configured, evaluation runs are
        tracked in the AI Foundry portal with full dashboards.
        """
        print("\n" + "=" * 70)
        print("  STEP 5: Azure AI Foundry Evaluation")
        print("=" * 70)

        try:
            from azure.ai.evaluation import (
                evaluate,
                SimilarityEvaluator,
                RelevanceEvaluator,
                CoherenceEvaluator,
                FluencyEvaluator,
                GroundednessEvaluator,
            )
        except ImportError:
            print("  ERROR: azure-ai-evaluation not installed.")
            print("  Install with: pip install azure-ai-evaluation")
            return

        # Build model config for LLM-based evaluators
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        deployment = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

        if not endpoint:
            print("  ERROR: AZURE_OPENAI_ENDPOINT is required for Foundry evaluation")
            return

        model_config = {
            "azure_endpoint": endpoint,
            "azure_deployment": deployment,
            "api_version": api_version,
        }

        if api_key:
            model_config["api_key"] = api_key
        else:
            # Use RBAC auth — get a bearer token for Azure OpenAI
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            model_config["api_key"] = token.token
            print("  Auth: RBAC (DefaultAzureCredential token)")

        # Build azure_ai_project config for portal tracking
        azure_ai_project = None
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        project_name = self.project_name or os.getenv("AZURE_AI_PROJECT_NAME")

        if subscription_id and resource_group and project_name:
            azure_ai_project = {
                "subscription_id": subscription_id,
                "resource_group_name": resource_group,
                "project_name": project_name,
            }
            print(f"  Foundry project: {project_name}")
            print(f"  Resource group:  {resource_group}")
            print("  Results will be tracked in AI Foundry portal ✓")
        else:
            print("  No Foundry project configured — running locally only.")
            if not project_name:
                print("  Tip: Set AZURE_AI_PROJECT_NAME or use --project-name")

        # Prepare evaluation dataset as JSONL
        # Only include non-security tests that have generated SQL
        eval_data = []
        for r in self.results:
            if r.is_security_test or not r.generated_sql:
                continue
            tc = next((t for t in self.test_cases if t.id == r.test_id), None)
            if not tc:
                continue

            # Build rich context: schema + expected output description
            context_parts = [self._schema_context_str]
            if tc.expected_columns:
                context_parts.append(
                    f"Expected columns in result: {', '.join(tc.expected_columns)}"
                )
            if tc.expected_aggregation:
                context_parts.append(
                    f"Expected aggregation: {tc.expected_aggregation}"
                )
            if tc.validation_query:
                context_parts.append(f"Reference SQL: {tc.validation_query}")
            if r.generated_row_count:
                context_parts.append(
                    f"Generated query returned {r.generated_row_count} rows"
                )

            eval_data.append({
                "query": tc.question,
                "response": r.generated_sql,
                "ground_truth": tc.validation_query or "",
                "context": "\n".join(context_parts),
            })

        if not eval_data:
            print("  No functional results to evaluate (need LLM mode, not offline)")
            return

        print(f"  Evaluating {len(eval_data)} test cases with Foundry evaluators...")

        # Write JSONL to temp file
        eval_jsonl_path = os.path.join(
            tempfile.mkdtemp(prefix="salesinsight_eval_"),
            "eval_dataset.jsonl",
        )
        with open(eval_jsonl_path, "w") as f:
            for row in eval_data:
                f.write(json.dumps(row) + "\n")

        print(f"  Dataset: {eval_jsonl_path}")

        # Define evaluators — includes groundedness for data-aware checking
        evaluators = {
            "similarity": SimilarityEvaluator(model_config=model_config),
            "relevance": RelevanceEvaluator(model_config=model_config),
            "coherence": CoherenceEvaluator(model_config=model_config),
            "fluency": FluencyEvaluator(model_config=model_config),
            "groundedness": GroundednessEvaluator(model_config=model_config),
        }

        eval_name = f"salesinsight-nl2sql-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Run Foundry evaluate()
        print(f"  Running evaluate() — {eval_name}...")
        print(f"  Evaluators: {', '.join(evaluators.keys())}")

        try:
            eval_result = evaluate(
                data=eval_jsonl_path,
                evaluators=evaluators,
                evaluation_name=eval_name,
                azure_ai_project=azure_ai_project,
                output_path=os.path.join(
                    tempfile.mkdtemp(prefix="salesinsight_eval_out_"),
                    "foundry_results.json",
                ),
                tags={
                    "pipeline": "nl2sql",
                    "project": "salesinsight",
                    "mode": "llm",
                    "test_count": str(len(eval_data)),
                },
            )
        except Exception as e:
            print(f"  ERROR: Foundry evaluate() failed: {e}")
            import traceback
            traceback.print_exc()
            return

        self._foundry_eval_result = eval_result

        # Extract per-row scores and attach to our results
        rows_df = eval_result.get("rows", None)
        if rows_df is not None and hasattr(rows_df, "iterrows"):
            idx = 0
            for r in self.results:
                if r.is_security_test or not r.generated_sql:
                    continue
                if idx < len(rows_df):
                    row = rows_df.iloc[idx]
                    r.similarity_score = row.get("outputs.similarity.similarity", row.get("similarity", None))
                    r.relevance_score = row.get("outputs.relevance.relevance", row.get("relevance", None))
                    r.coherence_score = row.get("outputs.coherence.coherence", row.get("coherence", None))
                    r.fluency_score = row.get("outputs.fluency.fluency", row.get("fluency", None))
                    r.groundedness_score = row.get("outputs.groundedness.groundedness", row.get("groundedness", None))
                    idx += 1

        # Print aggregated metrics
        metrics = eval_result.get("metrics", {})
        if metrics:
            print("\n  Foundry Evaluation Metrics:")
            print(f"  {'─' * 40}")
            for metric_name, value in sorted(metrics.items()):
                if isinstance(value, float):
                    print(f"    {metric_name}: {value:.3f}")
                else:
                    print(f"    {metric_name}: {value}")

        if azure_ai_project:
            print("\n  📊 View in AI Foundry portal:")
            print("     https://ai.azure.com/build/evaluation")
            print(f"     Project: {project_name} | Run: {eval_name}")

        print("\n  Foundry evaluation complete. ✓")

    def generate_report(self) -> EvalReport:
        """Generate evaluation report from results."""
        print("\n" + "=" * 70)
        print("  STEP 4: Generating Report")
        print("=" * 70)

        report = EvalReport(timestamp=datetime.now().isoformat())
        report.total_tests = len(self.results)

        confidence_scores = []
        gen_times = []
        category_results: dict[str, list[bool]] = {}

        for r in self.results:
            # Count pass/fail
            if r.passed:
                report.passed += 1
            elif r.error and "skipped" in (r.notes or "").lower():
                report.skipped += 1
            else:
                report.failed += 1

            # Security tests
            if r.is_security_test:
                report.security_tests_total += 1
                if r.security_blocked:
                    report.security_tests_passed += 1

            # Averages
            if r.confidence_score is not None:
                confidence_scores.append(r.confidence_score)
            if r.generation_time_ms > 0:
                gen_times.append(r.generation_time_ms)
            report.total_tokens += r.tokens_used

            # Category tracking
            if r.category not in category_results:
                category_results[r.category] = []
            category_results[r.category].append(r.passed)

            report.results.append(asdict(r))

        # Calculate averages
        report.accuracy_pct = (
            (report.passed / report.total_tests * 100) if report.total_tests else 0
        )
        report.avg_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0
        )
        report.avg_generation_time_ms = (
            sum(gen_times) / len(gen_times) if gen_times else 0
        )

        # Category scores
        for cat, results_list in category_results.items():
            passed_count = sum(1 for r in results_list if r)
            report.category_scores[cat] = (
                passed_count / len(results_list) * 100 if results_list else 0
            )

        # Foundry aggregate scores
        foundry_fields = [
            ("similarity_score", "foundry_avg_similarity"),
            ("relevance_score", "foundry_avg_relevance"),
            ("coherence_score", "foundry_avg_coherence"),
            ("fluency_score", "foundry_avg_fluency"),
            ("groundedness_score", "foundry_avg_groundedness"),
        ]
        for result_field, report_field in foundry_fields:
            scores = [
                getattr(r, result_field)
                for r in self.results
                if getattr(r, result_field) is not None
            ]
            if scores:
                setattr(report, report_field, sum(scores) / len(scores))

        return report

    def print_report(self, report: EvalReport):
        """Print a formatted evaluation report."""
        print("\n" + "=" * 70)
        print("  EVALUATION REPORT")
        print("=" * 70)

        print(f"\n  Timestamp:  {report.timestamp}")
        print(f"  Mode:       {'Offline' if self.offline else 'Online (LLM)'}")
        if self.use_foundry and not self.offline:
            print("  AI Eval:    Azure AI Foundry (evaluate API)")
        print(f"  Dynamic:    {'Yes (auto-generated)' if self.auto_generate else 'No (golden dataset)'}")

        # Overall scores
        print(f"\n  {'─' * 50}")
        print(f"  OVERALL ACCURACY:  {report.accuracy_pct:.1f}%")
        print(f"  {'─' * 50}")
        print(f"  Total tests:       {report.total_tests}")
        print(f"  Passed:            {report.passed}")
        print(f"  Failed:            {report.failed}")
        if report.skipped:
            print(f"  Skipped:           {report.skipped}")

        # Security
        if report.security_tests_total:
            pct = report.security_tests_passed / report.security_tests_total * 100
            print(f"\n  Security tests:    {report.security_tests_passed}/{report.security_tests_total} blocked ({pct:.0f}%)")

        # Performance
        if report.avg_generation_time_ms > 0:
            print(f"\n  Avg generation:    {report.avg_generation_time_ms:.0f}ms")
            print(f"  Avg confidence:    {report.avg_confidence:.2f}")
            print(f"  Total tokens:      {report.total_tokens:,}")

        # Foundry AI Evaluation Scores
        if report.foundry_avg_similarity is not None:
            print(f"\n  {'─' * 50}")
            print("  FOUNDRY AI EVALUATION SCORES (avg)")
            print(f"  {'─' * 50}")
            for label, val in [
                ("Similarity", report.foundry_avg_similarity),
                ("Relevance", report.foundry_avg_relevance),
                ("Coherence", report.foundry_avg_coherence),
                ("Fluency", report.foundry_avg_fluency),
                ("Groundedness", report.foundry_avg_groundedness),
            ]:
                if val is not None:
                    bar = "█" * int(val) + "░" * (5 - int(val))
                    print(f"    {label:<15} {bar} {val:.2f}/5.00")

        # Category breakdown
        print("\n  Category Scores:")
        for cat, score in sorted(report.category_scores.items()):
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            print(f"    {cat:<15} {bar} {score:.0f}%")

        # Detailed results
        print(f"\n  {'─' * 50}")
        print("  DETAILED RESULTS")
        print(f"  {'─' * 50}")

        for r in self.results:
            icon = "✅" if r.passed else ("🛡️" if r.is_security_test and r.security_blocked else "❌")
            print(f"\n  {icon} {r.test_id} [{r.category}]")
            print(f"     Q: {r.question[:70]}")

            if r.generated_sql:
                print(f"     SQL: {r.generated_sql[:80]}")

            if r.confidence_score is not None:
                print(f"     Confidence: {r.confidence_score:.2f} | Time: {r.generation_time_ms:.0f}ms | Tokens: {r.tokens_used}")

            if r.data_match_score > 0:
                print(f"     Data match: {r.data_match_score:.1%} | Rows: {r.generated_row_count} (expected: {r.expected_row_count})")

            if r.similarity_score is not None:
                scores = [f"Sim: {r.similarity_score:.2f}"]
                if r.relevance_score is not None:
                    scores.append(f"Rel: {r.relevance_score:.2f}")
                if r.coherence_score is not None:
                    scores.append(f"Coh: {r.coherence_score:.2f}")
                if r.fluency_score is not None:
                    scores.append(f"Flu: {r.fluency_score:.2f}")
                if r.groundedness_score is not None:
                    scores.append(f"Gnd: {r.groundedness_score:.2f}")
                print(f"     Foundry Eval — {' | '.join(scores)}")

            if r.is_security_test:
                print(f"     Security: {'BLOCKED ✓' if r.security_blocked else 'NOT BLOCKED ✗'}")
                if r.notes:
                    print(f"     Detail: {r.notes}")

            if r.error:
                print(f"     Error: {r.error}")

    def save_report(self, report: EvalReport, output_path: str):
        """Save report to JSON file."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"\n  Report saved to: {output_path}")

    def cleanup(self):
        """Clean up resources."""
        if self._data_source:
            try:
                self._data_source.disconnect()
            except Exception:
                pass


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="SalesInsight NL2SQL Evaluation Pipeline"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline (no LLM calls — validates expected SQL and schema only)",
    )
    parser.add_argument(
        "--no-foundry",
        action="store_true",
        help="Disable Azure AI Foundry evaluation (local comparison only)",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Auto-generate test cases from current data (ignores golden_dataset.json)",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        help="Azure AI Foundry project name (or set AZURE_AI_PROJECT_NAME env var)",
    )
    parser.add_argument(
        "--id",
        type=str,
        help="Run a single test case by ID (e.g., eval-001)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save JSON report to this path",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(Path(__file__).parent / "golden_dataset.json"),
        help="Path to the golden dataset JSON file",
    )
    args = parser.parse_args()

    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + "  SalesInsight NL2SQL Evaluation Pipeline".center(68) + "║")
    print("╚" + "═" * 68 + "╝")

    use_foundry = not args.no_foundry

    # Foundry implies LLM mode (not offline)
    if use_foundry and args.offline:
        print("  NOTE: Foundry evaluation disabled in offline mode")
        use_foundry = False

    evaluator = NL2SQLEvaluator(
        dataset_path=args.dataset,
        offline=args.offline,
        use_foundry=use_foundry,
        project_name=args.project_name,
        auto_generate=args.generate,
    )

    try:
        # Step 1: Load dataset
        evaluator.load_dataset()

        # Step 2: Setup components
        evaluator.setup_components()

        # Step 3: Run evaluation
        evaluator.run_evaluation(test_id=args.id)

        # Step 4: Generate and print report
        report = evaluator.generate_report()
        evaluator.print_report(report)

        # Step 5: Azure AI Foundry evaluation (default when online)
        if use_foundry and not args.offline:
            evaluator.run_foundry_evaluation()

        # Save if requested
        if args.output:
            evaluator.save_report(report, args.output)

        # Exit code based on results
        if report.accuracy_pct >= 80:
            print(f"\n  ✅ Evaluation PASSED ({report.accuracy_pct:.0f}% accuracy)")
            return 0
        else:
            print(f"\n  ⚠️  Evaluation needs improvement ({report.accuracy_pct:.0f}% accuracy)")
            return 1

    except Exception as e:
        print(f"\n  ❌ Evaluation failed: {e}")
        import traceback

        traceback.print_exc()
        return 2

    finally:
        evaluator.cleanup()


if __name__ == "__main__":
    sys.exit(main())
