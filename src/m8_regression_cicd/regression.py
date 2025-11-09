"""
Module 8.3: Regression Testing & CI/CD for RAG Systems

This module implements automated quality assurance for RAG systems including:
- Regression test suite for quality metrics (faithfulness, relevancy, precision)
- Performance benchmarking (latency, cost)
- DVC model versioning and rollback
- Safe deployment with canary testing
- Threshold calibration and flaky test handling

Key Thresholds (from script):
- Faithfulness: ≥0.75
- Answer Relevancy: ≥0.70
- Context Precision: ≥0.65
- P95 Latency: ≤2000ms
- Cost per Query: ≤$0.01
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import statistics
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class RegressionMetrics:
    """Regression test metrics with thresholds from script."""
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    p95_latency_ms: float
    cost_per_query: float

    # Thresholds from script
    FAITHFULNESS_THRESHOLD = 0.75
    RELEVANCY_THRESHOLD = 0.70
    PRECISION_THRESHOLD = 0.65
    LATENCY_THRESHOLD_MS = 2000
    COST_THRESHOLD = 0.01

    def passes_thresholds(self) -> Tuple[bool, List[str]]:
        """Check if metrics pass all thresholds. Returns (passes, failures)."""
        failures = []

        if self.faithfulness < self.FAITHFULNESS_THRESHOLD:
            failures.append(f"Faithfulness {self.faithfulness:.3f} < {self.FAITHFULNESS_THRESHOLD}")
        if self.answer_relevancy < self.RELEVANCY_THRESHOLD:
            failures.append(f"Answer Relevancy {self.answer_relevancy:.3f} < {self.RELEVANCY_THRESHOLD}")
        if self.context_precision < self.PRECISION_THRESHOLD:
            failures.append(f"Context Precision {self.context_precision:.3f} < {self.PRECISION_THRESHOLD}")
        if self.p95_latency_ms > self.LATENCY_THRESHOLD_MS:
            failures.append(f"P95 Latency {self.p95_latency_ms:.0f}ms > {self.LATENCY_THRESHOLD_MS}ms")
        if self.cost_per_query > self.COST_THRESHOLD:
            failures.append(f"Cost per query ${self.cost_per_query:.4f} > ${self.COST_THRESHOLD}")

        return len(failures) == 0, failures


@dataclass
class TestResult:
    """Single test execution result."""
    test_name: str
    passed: bool
    metric_value: float
    threshold: float
    execution_time_ms: float
    error: Optional[str] = None


# ============================================================================
# REGRESSION TEST SUITE
# ============================================================================

class RegressionTestSuite:
    """
    Regression test suite for RAG systems.

    Uses 50-question subset (runs ~3 minutes) vs full 500-question set (20 minutes).
    Script trade-off: Speed vs thoroughness.
    """

    def __init__(self, test_data: List[Dict[str, Any]], use_subset: bool = True):
        """
        Initialize test suite.

        Args:
            test_data: List of test questions with expected answers
            use_subset: If True, use 50-question subset for fast CI
        """
        self.test_data = test_data[:50] if use_subset else test_data
        logger.info(f"Initialized test suite with {len(self.test_data)} questions")

    def run_quality_tests(self, rag_pipeline: Any) -> RegressionMetrics:
        """
        Run full regression test suite.

        Script note: Tests faithfulness, relevancy, precision, latency, and cost.

        Args:
            rag_pipeline: RAG pipeline to test (must have .query() method)

        Returns:
            RegressionMetrics with all scores

        Raises:
            ValueError: If test data is empty or rag_pipeline is invalid
        """
        if not self.test_data:
            raise ValueError("Test data is empty")

        logger.info("Starting regression test suite...")
        start_time = time.time()

        # Collect metrics
        faithfulness_scores = []
        relevancy_scores = []
        precision_scores = []
        latencies = []
        costs = []

        for i, test_case in enumerate(self.test_data):
            try:
                query_start = time.time()
                result = self._run_single_query(rag_pipeline, test_case)
                query_time = (time.time() - query_start) * 1000  # Convert to ms

                faithfulness_scores.append(result['faithfulness'])
                relevancy_scores.append(result['relevancy'])
                precision_scores.append(result['precision'])
                latencies.append(query_time)
                costs.append(result['cost'])

                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(self.test_data)} queries")

            except Exception as e:
                logger.error(f"Failed on query {i}: {e}")
                # Use worst-case values for failed queries
                faithfulness_scores.append(0.0)
                relevancy_scores.append(0.0)
                precision_scores.append(0.0)
                latencies.append(5000.0)  # 5s timeout
                costs.append(0.02)

        # Calculate aggregates
        metrics = RegressionMetrics(
            faithfulness=statistics.mean(faithfulness_scores),
            answer_relevancy=statistics.mean(relevancy_scores),
            context_precision=statistics.mean(precision_scores),
            p95_latency_ms=self._calculate_p95(latencies),
            cost_per_query=statistics.mean(costs)
        )

        elapsed = time.time() - start_time
        logger.info(f"Test suite completed in {elapsed:.1f}s")
        logger.info(f"Results: {metrics}")

        return metrics

    def _run_single_query(self, rag_pipeline: Any, test_case: Dict[str, Any]) -> Dict[str, float]:
        """
        Run single query and calculate metrics.

        Script note: Real implementation would use RAGAS evaluators.
        This is a mock implementation for demonstration.
        """
        question = test_case['question']
        expected_answer = test_case.get('expected_answer', '')
        expected_contexts = test_case.get('contexts', [])

        # Mock RAG query (replace with actual pipeline call)
        try:
            if hasattr(rag_pipeline, 'query'):
                response = rag_pipeline.query(question)
                answer = response.get('answer', '')
                contexts = response.get('contexts', [])
            else:
                # Fallback for testing without real pipeline
                answer = f"Mock answer for: {question}"
                contexts = ["Mock context 1", "Mock context 2"]
        except Exception as e:
            logger.warning(f"Pipeline query failed: {e}, using mock data")
            answer = f"Mock answer for: {question}"
            contexts = ["Mock context 1"]

        # Mock metric calculations (replace with RAGAS evaluators)
        # In production, use: from ragas.metrics import faithfulness, answer_relevancy, context_precision
        faithfulness = self._mock_faithfulness(answer, contexts)
        relevancy = self._mock_relevancy(answer, question)
        precision = self._mock_precision(contexts, expected_contexts)
        cost = self._estimate_cost(question, answer, contexts)

        return {
            'faithfulness': faithfulness,
            'relevancy': relevancy,
            'precision': precision,
            'cost': cost
        }

    def _mock_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """Mock faithfulness calculation. Replace with RAGAS in production."""
        # Simplified: check if answer content appears in contexts
        if not answer or not contexts:
            return 0.0
        # Simple heuristic: return value between 0.6 and 0.9
        return min(0.9, 0.6 + len(contexts) * 0.1)

    def _mock_relevancy(self, answer: str, question: str) -> float:
        """Mock relevancy calculation. Replace with RAGAS in production."""
        if not answer or not question:
            return 0.0
        # Simple heuristic: longer answers tend to be more relevant (naive)
        return min(0.9, 0.5 + len(answer) / 500)

    def _mock_precision(self, retrieved_contexts: List[str], expected_contexts: List[str]) -> float:
        """Mock precision calculation. Replace with RAGAS in production."""
        if not retrieved_contexts:
            return 0.0
        if not expected_contexts:
            return 0.7  # Default if no ground truth
        # Simple overlap check
        return min(0.9, 0.4 + len(retrieved_contexts) * 0.15)

    def _estimate_cost(self, question: str, answer: str, contexts: List[str]) -> float:
        """
        Estimate API cost per query.

        Script note: Target ≤$0.01 per query.
        Typical costs: GPT-4: ~$0.015, GPT-3.5: ~$0.003, embeddings: ~$0.0001
        """
        # Rough estimation based on token counts
        input_tokens = len(question.split()) + sum(len(ctx.split()) for ctx in contexts)
        output_tokens = len(answer.split())

        # Assume GPT-3.5 pricing: $0.0015/1K input, $0.002/1K output
        input_cost = (input_tokens / 1000) * 0.0015
        output_cost = (output_tokens / 1000) * 0.002
        embedding_cost = 0.0001  # Fixed cost for embeddings

        return input_cost + output_cost + embedding_cost

    def _calculate_p95(self, values: List[float]) -> float:
        """Calculate 95th percentile."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * 0.95)
        return sorted_values[min(index, len(sorted_values) - 1)]


# ============================================================================
# FLAKY TEST HANDLING
# ============================================================================

class FlakyTestHandler:
    """
    Handle flaky tests by running multiple times and using median.

    Script note: Common Failure #2 - Intermittent test failures due to
    infrastructure variance. Solution: Run 5 times, use median, apply ±20% tolerance.
    """

    def __init__(self, num_runs: int = 5, tolerance_pct: float = 20.0):
        """
        Initialize flaky test handler.

        Args:
            num_runs: Number of times to run test (default 5 from script)
            tolerance_pct: Tolerance band percentage (default ±20% from script)
        """
        self.num_runs = num_runs
        self.tolerance_pct = tolerance_pct

    def run_stable_test(self, test_func: callable, *args, **kwargs) -> Tuple[float, List[float]]:
        """
        Run test multiple times and return median value.

        Args:
            test_func: Test function to run
            *args, **kwargs: Arguments to pass to test function

        Returns:
            Tuple of (median_value, all_values)
        """
        logger.info(f"Running test {self.num_runs} times for stability...")
        values = []

        for run in range(self.num_runs):
            try:
                result = test_func(*args, **kwargs)
                values.append(result)
                logger.info(f"Run {run + 1}/{self.num_runs}: {result:.3f}")
            except Exception as e:
                logger.error(f"Run {run + 1} failed: {e}")
                values.append(0.0)

        if not values:
            logger.error("All test runs failed")
            return 0.0, []

        median_value = statistics.median(values)
        logger.info(f"Median value: {median_value:.3f}")
        return median_value, values

    def is_within_baseline(self, current_value: float, baseline: float) -> bool:
        """
        Check if current value is within tolerance of baseline.

        Args:
            current_value: Current metric value
            baseline: Baseline value to compare against

        Returns:
            True if within tolerance, False otherwise
        """
        lower_bound = baseline * (1 - self.tolerance_pct / 100)
        upper_bound = baseline * (1 + self.tolerance_pct / 100)
        within_bounds = lower_bound <= current_value <= upper_bound

        logger.info(f"Baseline: {baseline:.3f}, Current: {current_value:.3f}, "
                   f"Bounds: [{lower_bound:.3f}, {upper_bound:.3f}], Within: {within_bounds}")

        return within_bounds


# ============================================================================
# THRESHOLD CALIBRATION
# ============================================================================

class ThresholdCalibrator:
    """
    Calibrate regression thresholds using historical data.

    Script note: Common Failure #3 - Wrong thresholds cause false positives/negatives.
    Solution: Set threshold to baseline minus 2 standard deviations, target 2-5% false positive rate.
    """

    def __init__(self, baseline_file: Path = Path("baseline_metrics.json")):
        """Initialize threshold calibrator with baseline file."""
        self.baseline_file = baseline_file
        self.baselines: Dict[str, List[float]] = {}
        self._load_baselines()

    def _load_baselines(self) -> None:
        """Load historical baseline data."""
        if self.baseline_file.exists():
            try:
                with open(self.baseline_file, 'r') as f:
                    self.baselines = json.load(f)
                logger.info(f"Loaded baselines from {self.baseline_file}")
            except Exception as e:
                logger.error(f"Failed to load baselines: {e}")
                self.baselines = {}
        else:
            logger.info("No baseline file found, starting fresh")
            self.baselines = {}

    def add_measurement(self, metric_name: str, value: float) -> None:
        """Add a new measurement to baseline history."""
        if metric_name not in self.baselines:
            self.baselines[metric_name] = []
        self.baselines[metric_name].append(value)
        logger.info(f"Added {metric_name}={value:.3f} to baselines")

    def save_baselines(self) -> None:
        """Save baselines to disk."""
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(self.baselines, f, indent=2)
            logger.info(f"Saved baselines to {self.baseline_file}")
        except Exception as e:
            logger.error(f"Failed to save baselines: {e}")

    def calculate_threshold(self, metric_name: str, num_std: float = 2.0) -> Optional[float]:
        """
        Calculate threshold as baseline minus N standard deviations.

        Script guidance: baseline - 2*std targets 2-5% false positive rate.

        Args:
            metric_name: Name of metric
            num_std: Number of standard deviations (default 2.0 from script)

        Returns:
            Calculated threshold or None if insufficient data
        """
        if metric_name not in self.baselines or len(self.baselines[metric_name]) < 10:
            logger.warning(f"Insufficient data for {metric_name} (need ≥10 samples)")
            return None

        values = self.baselines[metric_name]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        threshold = mean - (num_std * stdev)

        logger.info(f"{metric_name}: mean={mean:.3f}, std={stdev:.3f}, threshold={threshold:.3f}")
        return threshold

    def get_recommended_thresholds(self) -> Dict[str, float]:
        """Get all recommended thresholds based on baselines."""
        thresholds = {}
        for metric_name in self.baselines:
            threshold = self.calculate_threshold(metric_name)
            if threshold is not None:
                thresholds[metric_name] = threshold
        return thresholds


# ============================================================================
# DVC VERSION MANAGER
# ============================================================================

class DVCVersionManager:
    """
    Manage model versions with DVC (Data Version Control).

    Script note: Step 3 - Track models/embeddings/prompts like code using S3 remote.
    Enables instant rollback capability.
    """

    def __init__(self, dvc_dir: Path = Path(".dvc"), models_dir: Path = Path("models")):
        """
        Initialize DVC version manager.

        Args:
            dvc_dir: DVC configuration directory
            models_dir: Directory containing models to version
        """
        self.dvc_dir = dvc_dir
        self.models_dir = models_dir
        self.models_dir.mkdir(exist_ok=True)

    def create_version(self, version_tag: Optional[str] = None) -> str:
        """
        Create a new version snapshot.

        Args:
            version_tag: Optional tag (defaults to timestamp)

        Returns:
            Version identifier

        Raises:
            RuntimeError: If DVC operations fail
        """
        if version_tag is None:
            version_tag = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info(f"Creating version: {version_tag}")

        try:
            # Add models to DVC tracking
            result = subprocess.run(
                ["dvc", "add", str(self.models_dir)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                logger.warning(f"DVC add warning: {result.stderr}")

            # Commit DVC files to git
            subprocess.run(
                ["git", "add", f"{self.models_dir}.dvc", ".gitignore"],
                capture_output=True, text=True, timeout=10
            )

            subprocess.run(
                ["git", "commit", "-m", f"Version {version_tag}"],
                capture_output=True, text=True, timeout=10
            )

            # Tag the commit
            subprocess.run(
                ["git", "tag", "-a", version_tag, "-m", f"Model version {version_tag}"],
                capture_output=True, text=True, timeout=10
            )

            logger.info(f"Created version {version_tag}")
            return version_tag

        except subprocess.TimeoutExpired:
            logger.error("DVC operation timed out")
            raise RuntimeError("DVC operation timed out")
        except Exception as e:
            logger.error(f"Failed to create version: {e}")
            raise RuntimeError(f"Version creation failed: {e}")

    def rollback_to_version(self, version_tag: str) -> bool:
        """
        Rollback to a specific version.

        Script note: Common Failure #5 - Previous versions lost. Ensure S3 retains
        minimum 10 versions for 90 days.

        Args:
            version_tag: Version to rollback to

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Rolling back to version: {version_tag}")

        try:
            # Checkout git tag
            result = subprocess.run(
                ["git", "checkout", version_tag],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                logger.error(f"Git checkout failed: {result.stderr}")
                return False

            # Pull DVC-tracked files
            result = subprocess.run(
                ["dvc", "pull"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                logger.error(f"DVC pull failed: {result.stderr}")
                return False

            logger.info(f"Successfully rolled back to {version_tag}")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Rollback operation timed out")
            return False
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def list_versions(self) -> List[str]:
        """List all available versions."""
        try:
            result = subprocess.run(
                ["git", "tag", "-l"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                versions = [v.strip() for v in result.stdout.split('\n') if v.strip()]
                logger.info(f"Found {len(versions)} versions")
                return versions
            else:
                logger.error("Failed to list versions")
                return []
        except Exception as e:
            logger.error(f"Failed to list versions: {e}")
            return []

    def verify_rollback_possible(self, version_tag: str) -> bool:
        """
        Verify that rollback to version is possible.

        Script note: Verify rollback before deploying new version.
        """
        versions = self.list_versions()
        available = version_tag in versions
        logger.info(f"Version {version_tag} {'is' if available else 'is NOT'} available for rollback")
        return available


# ============================================================================
# SAFE DEPLOYMENT
# ============================================================================

class SafeDeployment:
    """
    Safe deployment with canary testing and automatic rollback.

    Script note: Step 4 - Automated rollback on test failure.
    Tests on 10 canary queries, rollback if <80% pass rate.
    """

    def __init__(self, test_suite: RegressionTestSuite, version_manager: DVCVersionManager):
        """
        Initialize safe deployment.

        Args:
            test_suite: Regression test suite
            version_manager: DVC version manager for rollback
        """
        self.test_suite = test_suite
        self.version_manager = version_manager
        self.canary_size = 10  # From script: 10 canary queries
        self.pass_threshold = 0.80  # From script: 80% pass rate

    def deploy_with_canary(
        self,
        rag_pipeline: Any,
        new_version: str,
        previous_version: str
    ) -> Tuple[bool, str]:
        """
        Deploy with canary testing and automatic rollback.

        Args:
            rag_pipeline: RAG pipeline to test
            new_version: New version identifier
            previous_version: Previous version to rollback to if needed

        Returns:
            Tuple of (success, message)
        """
        logger.info(f"Starting canary deployment: {new_version}")

        # Verify rollback is possible before deploying
        if not self.version_manager.verify_rollback_possible(previous_version):
            return False, f"Cannot verify rollback to {previous_version} - aborting deployment"

        # Run canary tests (subset of test data)
        canary_data = self.test_suite.test_data[:self.canary_size]
        logger.info(f"Running canary test with {len(canary_data)} queries...")

        passed = 0
        failed = 0

        for test_case in canary_data:
            try:
                result = self.test_suite._run_single_query(rag_pipeline, test_case)

                # Check if query passes minimum thresholds
                if (result['faithfulness'] >= RegressionMetrics.FAITHFULNESS_THRESHOLD * 0.9 and
                    result['relevancy'] >= RegressionMetrics.RELEVANCY_THRESHOLD * 0.9):
                    passed += 1
                else:
                    failed += 1
                    logger.warning(f"Canary query failed: {test_case.get('question', 'N/A')[:50]}...")

            except Exception as e:
                failed += 1
                logger.error(f"Canary query error: {e}")

        pass_rate = passed / len(canary_data) if canary_data else 0
        logger.info(f"Canary pass rate: {pass_rate:.1%} ({passed}/{len(canary_data)})")

        if pass_rate >= self.pass_threshold:
            logger.info(f"✓ Canary passed ({pass_rate:.1%} ≥ {self.pass_threshold:.1%})")
            return True, f"Deployment successful: {new_version}"
        else:
            logger.error(f"✗ Canary failed ({pass_rate:.1%} < {self.pass_threshold:.1%})")
            logger.info(f"Initiating automatic rollback to {previous_version}...")

            if self.version_manager.rollback_to_version(previous_version):
                return False, f"Deployment failed, rolled back to {previous_version}"
            else:
                return False, f"Deployment failed AND rollback failed - manual intervention required"


# ============================================================================
# DVC MERGE CONFLICT RESOLVER
# ============================================================================

class DVCConflictResolver:
    """
    Resolve DVC merge conflicts by testing both versions.

    Script note: Common Failure #4 - Simultaneous model changes create conflicting
    MD5 hashes. Solution: Test both versions, choose better faithfulness score.
    """

    def __init__(self, test_suite: RegressionTestSuite):
        """Initialize conflict resolver."""
        self.test_suite = test_suite

    def resolve_conflict(
        self,
        version_a: str,
        version_b: str,
        rag_pipeline_factory: callable
    ) -> str:
        """
        Resolve conflict by testing both versions.

        Args:
            version_a: First conflicting version
            version_b: Second conflicting version
            rag_pipeline_factory: Function to create RAG pipeline for a version

        Returns:
            Version identifier of the winner
        """
        logger.info(f"Resolving DVC conflict between {version_a} and {version_b}")

        # Test version A
        logger.info(f"Testing version {version_a}...")
        pipeline_a = rag_pipeline_factory(version_a)
        metrics_a = self.test_suite.run_quality_tests(pipeline_a)
        score_a = metrics_a.faithfulness

        # Test version B
        logger.info(f"Testing version {version_b}...")
        pipeline_b = rag_pipeline_factory(version_b)
        metrics_b = self.test_suite.run_quality_tests(pipeline_b)
        score_b = metrics_b.faithfulness

        # Choose winner
        if score_a >= score_b:
            winner = version_a
            logger.info(f"✓ {version_a} wins (faithfulness: {score_a:.3f} vs {score_b:.3f})")
        else:
            winner = version_b
            logger.info(f"✓ {version_b} wins (faithfulness: {score_b:.3f} vs {score_a:.3f})")

        return winner


# ============================================================================
# CI/CD COST ESTIMATOR
# ============================================================================

def estimate_cicd_costs(deploys_per_month: int, team_size: int) -> Dict[str, float]:
    """
    Estimate CI/CD costs based on deployment frequency and team size.

    Script cost scaling:
    - 10 deploys/month: $50-80
    - 50 deploys/month: $150-200
    - 100+ deploys/month: $500-800

    Args:
        deploys_per_month: Number of deployments per month
        team_size: Number of team members

    Returns:
        Dict with cost breakdown
    """
    # GitHub Actions minutes cost
    minutes_per_deploy = 5  # From script: fast CI ~3-5 min
    total_minutes = deploys_per_month * minutes_per_deploy

    # Free tier: 2000 minutes/month
    billable_minutes = max(0, total_minutes - 2000)
    github_cost = billable_minutes * 0.008  # $0.008 per minute

    # Storage costs (DVC/S3)
    # Assume 1GB per model version, 90-day retention
    versions_stored = min(deploys_per_month * 3, 100)  # Keep ~3 months
    storage_cost = versions_stored * 0.023  # $0.023 per GB-month

    # API costs during testing
    queries_per_test = 50  # Script: 50-question subset
    cost_per_query = 0.003  # Typical GPT-3.5 cost
    api_cost = deploys_per_month * queries_per_test * cost_per_query

    total = github_cost + storage_cost + api_cost

    logger.info(f"Cost estimate for {deploys_per_month} deploys/month, {team_size} engineers:")
    logger.info(f"  GitHub Actions: ${github_cost:.2f}")
    logger.info(f"  Storage (S3):   ${storage_cost:.2f}")
    logger.info(f"  API Testing:    ${api_cost:.2f}")
    logger.info(f"  Total:          ${total:.2f}/month")

    return {
        'github_actions': github_cost,
        'storage': storage_cost,
        'api_testing': api_cost,
        'total': total
    }


# ============================================================================
# DECISION HELPER
# ============================================================================

def should_use_cicd(
    deploys_per_month: int,
    team_size: int,
    budget_per_month: float,
    has_pmf: bool = True
) -> Tuple[bool, str]:
    """
    Determine if CI/CD is appropriate for this team/project.

    Script Decision Card:
    - Use when: 20-100 deploys/month, 3-10 engineers, $150+ budget, has PMF
    - Avoid when: <5 deploys/month, <3 engineers, <$200 budget, pre-PMF

    Args:
        deploys_per_month: Deployment frequency
        team_size: Number of engineers
        budget_per_month: Available monthly budget
        has_pmf: Whether product has product-market fit

    Returns:
        Tuple of (should_use, reason)
    """
    reasons = []

    # Check deployment frequency
    if deploys_per_month < 5:
        return False, "Deploy <5 times/month - manual testing more efficient"

    # Check team size
    if team_size < 3:
        reasons.append("Team <3 people - overhead may outweigh benefits")

    # Check budget
    estimated_cost = estimate_cicd_costs(deploys_per_month, team_size)['total']
    if budget_per_month < estimated_cost:
        return False, f"Budget ${budget_per_month:.0f}/month insufficient (need ${estimated_cost:.0f})"

    # Check PMF
    if not has_pmf:
        return False, "Pre-PMF: requirements too unstable for regression testing"

    # Sweet spot: 20-100 deploys, 3-10 people
    if 20 <= deploys_per_month <= 100 and 3 <= team_size <= 10:
        return True, f"Ideal fit: {deploys_per_month} deploys/month, {team_size} engineers"

    # Edge cases
    if deploys_per_month > 100:
        return True, f"High velocity ({deploys_per_month} deploys/month) - consider managed platform"

    if team_size > 10:
        return True, f"Large team ({team_size} engineers) - needs CI/CD coordination"

    # Marginal cases
    if 5 <= deploys_per_month < 20:
        return True, f"Moderate velocity - CI/CD recommended but not critical"

    return True, "CI/CD recommended"


# ============================================================================
# CLI EXAMPLES
# ============================================================================

if __name__ == "__main__":
    """
    CLI usage examples for testing the module.
    """

    print("=" * 70)
    print("Module 8.3: Regression Testing & CI/CD for RAG Systems")
    print("=" * 70)
    print()

    # Example 1: Load test data and run regression tests
    print("Example 1: Regression Test Suite")
    print("-" * 70)

    # Mock test data
    test_data = [
        {
            'question': 'What is RAG?',
            'expected_answer': 'Retrieval Augmented Generation...',
            'contexts': ['RAG is a technique...']
        },
        {
            'question': 'How does CI/CD work?',
            'expected_answer': 'CI/CD automates testing...',
            'contexts': ['Continuous Integration...']
        }
    ] * 25  # Create 50 questions

    test_suite = RegressionTestSuite(test_data, use_subset=True)
    print(f"✓ Loaded test suite with {len(test_suite.test_data)} questions")
    print()

    # Example 2: Check if CI/CD is appropriate
    print("Example 2: Decision Helper")
    print("-" * 70)

    scenarios = [
        (5, 2, 100, True),   # Too small
        (50, 5, 200, True),  # Good fit
        (120, 15, 1000, True)  # Large scale
    ]

    for deploys, team, budget, pmf in scenarios:
        should_use, reason = should_use_cicd(deploys, team, budget, pmf)
        status = "✓ USE" if should_use else "✗ AVOID"
        print(f"{status}: {deploys} deploys/mo, {team} engineers, ${budget}/mo")
        print(f"   Reason: {reason}")
    print()

    # Example 3: Cost estimation
    print("Example 3: Cost Estimation")
    print("-" * 70)
    costs = estimate_cicd_costs(deploys_per_month=50, team_size=5)
    print()

    # Example 4: Threshold calibration
    print("Example 4: Threshold Calibration")
    print("-" * 70)
    calibrator = ThresholdCalibrator(Path("baseline_metrics_test.json"))

    # Simulate adding measurements
    for i in range(15):
        calibrator.add_measurement('faithfulness', 0.80 + (i % 10) * 0.01)

    threshold = calibrator.calculate_threshold('faithfulness')
    print(f"✓ Calculated faithfulness threshold: {threshold:.3f}")
    print()

    # Example 5: Flaky test handling
    print("Example 5: Flaky Test Handler")
    print("-" * 70)
    handler = FlakyTestHandler(num_runs=5, tolerance_pct=20.0)

    def mock_flaky_test():
        import random
        return 0.75 + random.uniform(-0.05, 0.05)

    median, all_values = handler.run_stable_test(mock_flaky_test)
    print(f"✓ Median value: {median:.3f}")
    print(f"  All values: {[f'{v:.3f}' for v in all_values]}")
    print()

    print("=" * 70)
    print("Module examples completed successfully!")
    print("=" * 70)
