"""
Module 8.2: A/B Testing for RAG Improvements

This module implements a complete A/B testing framework for scientifically
validating RAG system improvements before full production rollout.

Components:
- ExperimentConfig and ExperimentManager: Define and manage experiments
- TrafficSplitter: Random user assignment with consistent hashing
- ABTestingRAGPipeline: Integration with RAG query execution
- StatisticalAnalyzer: Statistical significance testing
- RolloutController: Gradual deployment management
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Literal, Tuple, List
import numpy as np
from scipy import stats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VariantType = Literal["control", "treatment"]


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment."""
    experiment_id: str
    name: str
    description: str
    control_config: Dict[str, Any]  # e.g., {"chunk_size": 512, "top_k": 5}
    treatment_config: Dict[str, Any]  # e.g., {"chunk_size": 1024, "top_k": 5}
    traffic_split: float = 0.5  # 0.5 = 50/50, 0.1 = 10% treatment
    min_sample_size: int = 1000  # Per variant
    significance_level: float = 0.05  # p-value threshold
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "running"  # running, paused, completed


class ExperimentManager:
    """Manages A/B testing experiments."""

    def __init__(self, db_connection=None):
        """
        Initialize experiment manager.

        Args:
            db_connection: Database connection (optional for demo mode)
        """
        self.db = db_connection
        self._experiments = {}  # In-memory fallback

    def create_experiment(self, config: ExperimentConfig) -> str:
        """
        Create a new experiment.

        Args:
            config: Experiment configuration

        Returns:
            Experiment ID
        """
        try:
            if self.db:
                query = """
                    INSERT INTO experiments
                    (experiment_id, name, description, control_config,
                     treatment_config, traffic_split, start_time, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.db.execute(query, (
                    config.experiment_id,
                    config.name,
                    config.description,
                    json.dumps(config.control_config),
                    json.dumps(config.treatment_config),
                    config.traffic_split,
                    config.start_time or datetime.now(),
                    config.status
                ))
                self.db.commit()
                logger.info(f"Created experiment: {config.experiment_id}")
            else:
                # In-memory fallback
                self._experiments[config.experiment_id] = config
                logger.info(f"Created in-memory experiment: {config.experiment_id}")

            return config.experiment_id
        except Exception as e:
            logger.error(f"Failed to create experiment: {e}")
            raise

    def get_active_experiments(self) -> List[ExperimentConfig]:
        """Get all currently running experiments."""
        try:
            if self.db:
                query = """
                    SELECT experiment_id, name, description, control_config,
                           treatment_config, traffic_split, start_time, status
                    FROM experiments
                    WHERE status = 'running'
                """
                results = self.db.execute(query).fetchall()

                experiments = []
                for row in results:
                    experiments.append(ExperimentConfig(
                        experiment_id=row[0],
                        name=row[1],
                        description=row[2],
                        control_config=json.loads(row[3]),
                        treatment_config=json.loads(row[4]),
                        traffic_split=row[5],
                        start_time=row[6],
                        status=row[7]
                    ))
                return experiments
            else:
                # In-memory fallback
                return [e for e in self._experiments.values() if e.status == "running"]
        except Exception as e:
            logger.error(f"Failed to get active experiments: {e}")
            return []

    def stop_experiment(self, experiment_id: str, winner: str):
        """
        Stop an experiment and record the winner.

        Args:
            experiment_id: Experiment to stop
            winner: 'control', 'treatment', or 'inconclusive'
        """
        try:
            if self.db:
                query = """
                    UPDATE experiments
                    SET status = 'completed',
                        end_time = %s,
                        winner = %s
                    WHERE experiment_id = %s
                """
                self.db.execute(query, (datetime.now(), winner, experiment_id))
                self.db.commit()
                logger.info(f"Stopped experiment {experiment_id}, winner: {winner}")
            else:
                # In-memory fallback
                if experiment_id in self._experiments:
                    self._experiments[experiment_id].status = "completed"
                    self._experiments[experiment_id].end_time = datetime.now()
                    logger.info(f"Stopped in-memory experiment {experiment_id}, winner: {winner}")
        except Exception as e:
            logger.error(f"Failed to stop experiment: {e}")


class TrafficSplitter:
    """Handles user assignment to experiment variants."""

    def __init__(self, db_connection=None):
        """
        Initialize traffic splitter.

        Args:
            db_connection: Database connection (optional for demo mode)
        """
        self.db = db_connection
        self._assignments = {}  # In-memory fallback

    def assign_variant(
        self,
        user_id: str,
        experiment_id: str,
        traffic_split: float
    ) -> VariantType:
        """
        Assign user to variant with consistent hashing.

        Uses cryptographic hashing for:
        1. Deterministic assignment (same user always gets same variant)
        2. Uniform distribution (unbiased)
        3. Independence from user characteristics

        Args:
            user_id: Unique identifier for user
            experiment_id: Experiment to assign to
            traffic_split: Percentage for treatment (0.5 = 50%)

        Returns:
            "control" or "treatment"
        """
        # Check if user already assigned
        existing = self._get_existing_assignment(user_id, experiment_id)
        if existing:
            return existing

        # Use deterministic hashing for assignment
        # This ensures same user always gets same variant
        hash_input = f"{user_id}:{experiment_id}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        # Convert first 8 hex chars to int, then to 0-1 range
        hash_number = int(hash_value[:8], 16) / (16**8)

        # Assign based on traffic_split threshold
        variant = "treatment" if hash_number < traffic_split else "control"

        # Store assignment for consistency
        self._store_assignment(user_id, experiment_id, variant)

        return variant

    def _get_existing_assignment(
        self,
        user_id: str,
        experiment_id: str
    ) -> Optional[VariantType]:
        """Check if user has existing assignment."""
        try:
            if self.db:
                query = """
                    SELECT variant
                    FROM experiment_assignments
                    WHERE user_id = %s AND experiment_id = %s
                """
                result = self.db.execute(query, (user_id, experiment_id)).fetchone()
                return result[0] if result else None
            else:
                # In-memory fallback
                key = f"{user_id}:{experiment_id}"
                return self._assignments.get(key)
        except Exception as e:
            logger.error(f"Failed to get existing assignment: {e}")
            return None

    def _store_assignment(
        self,
        user_id: str,
        experiment_id: str,
        variant: VariantType
    ):
        """Store user assignment for consistency."""
        try:
            if self.db:
                query = """
                    INSERT INTO experiment_assignments
                    (user_id, experiment_id, variant, assigned_at)
                    VALUES (%s, %s, %s, %s)
                """
                self.db.execute(query, (user_id, experiment_id, variant, datetime.now()))
                self.db.commit()
            else:
                # In-memory fallback
                key = f"{user_id}:{experiment_id}"
                self._assignments[key] = variant
        except Exception as e:
            logger.error(f"Failed to store assignment: {e}")

    def get_assignment_distribution(self, experiment_id: str) -> Dict[str, int]:
        """
        Get distribution of assignments (for monitoring).

        Args:
            experiment_id: Experiment to check

        Returns:
            Dictionary with counts per variant
        """
        try:
            if self.db:
                query = """
                    SELECT variant, COUNT(*) as count
                    FROM experiment_assignments
                    WHERE experiment_id = %s
                    GROUP BY variant
                """
                results = self.db.execute(query, (experiment_id,)).fetchall()
                return {row[0]: row[1] for row in results}
            else:
                # In-memory fallback
                distribution = {"control": 0, "treatment": 0}
                for key, variant in self._assignments.items():
                    if experiment_id in key:
                        distribution[variant] = distribution.get(variant, 0) + 1
                return distribution
        except Exception as e:
            logger.error(f"Failed to get assignment distribution: {e}")
            return {"control": 0, "treatment": 0}


class ABTestingRAGPipeline:
    """RAG pipeline with A/B testing support."""

    def __init__(
        self,
        base_retriever=None,
        base_llm=None,
        ragas_evaluator=None,
        db_connection=None
    ):
        """
        Initialize A/B testing RAG pipeline.

        Args:
            base_retriever: Retriever from Level 1 (optional for demo)
            base_llm: LLM from Level 1 (optional for demo)
            ragas_evaluator: RAGAS evaluator from M8.1 (optional for demo)
            db_connection: Database connection (optional for demo)
        """
        self.base_retriever = base_retriever
        self.base_llm = base_llm
        self.ragas_evaluator = ragas_evaluator
        self.db = db_connection
        self.experiment_manager = ExperimentManager(db_connection)
        self.traffic_splitter = TrafficSplitter(db_connection)
        self._results = []  # In-memory fallback for results

    def query(
        self,
        question: str,
        user_id: str,
        query_id: str
    ) -> Dict[str, Any]:
        """
        Execute RAG query with A/B testing.

        Args:
            question: User's question
            user_id: User identifier for consistent assignment
            query_id: Unique query identifier

        Returns:
            Response + variant + metrics
        """
        start_time = time.time()

        # Get active experiments
        active_experiments = self.experiment_manager.get_active_experiments()

        if not active_experiments:
            # No experiments running, use default config
            logger.info("No active experiments, using default config")
            return self._query_default(question, query_id)

        # For simplicity, use first active experiment
        experiment = active_experiments[0]

        # Assign user to variant
        variant = self.traffic_splitter.assign_variant(
            user_id,
            experiment.experiment_id,
            experiment.traffic_split
        )

        # Get config for this variant
        config = (
            experiment.control_config if variant == "control"
            else experiment.treatment_config
        )

        # Execute RAG query with variant-specific config
        contexts, response, metrics = self._execute_rag_with_config(question, config)

        latency_ms = int((time.time() - start_time) * 1000)

        # Store results for statistical analysis
        self._store_experiment_result(
            experiment_id=experiment.experiment_id,
            variant=variant,
            query_id=query_id,
            metrics=metrics,
            latency_ms=latency_ms
        )

        logger.info(f"Query {query_id}: variant={variant}, faithfulness={metrics.get('faithfulness', 0):.3f}")

        return {
            "response": response,
            "contexts": contexts,
            "metrics": metrics,
            "variant": variant,
            "experiment_id": experiment.experiment_id,
            "latency_ms": latency_ms
        }

    def _execute_rag_with_config(
        self,
        question: str,
        config: Dict[str, Any]
    ) -> Tuple[List[str], str, Dict[str, float]]:
        """Execute RAG with experiment-specific config."""
        # Simulate RAG execution if components not available
        if not self.base_retriever or not self.base_llm:
            logger.warning("⚠️ Skipping API calls (no retriever/LLM configured)")
            # Simulate results based on config
            chunk_size = config.get("chunk_size", 512)
            top_k = config.get("top_k", 5)

            contexts = [f"Context {i} (chunk_size={chunk_size})" for i in range(top_k)]
            response = f"Simulated response for: {question}"

            # Simulate metrics (larger chunk_size slightly better)
            base_faithfulness = 0.82
            if chunk_size > 512:
                base_faithfulness += 0.02

            metrics = {
                "faithfulness": base_faithfulness + np.random.normal(0, 0.05),
                "answer_relevance": 0.78 + np.random.normal(0, 0.05),
                "context_precision": 0.85 + np.random.normal(0, 0.03)
            }

            return contexts, response, metrics

        # Real execution
        chunk_size = config.get("chunk_size", 512)
        top_k = config.get("top_k", 5)
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 512)

        contexts = self.base_retriever.retrieve(
            question,
            top_k=top_k
        )

        response = self.base_llm.generate(
            question=question,
            contexts=contexts,
            temperature=temperature,
            max_tokens=max_tokens
        )

        metrics = self.ragas_evaluator.evaluate(
            question=question,
            contexts=contexts,
            response=response
        )

        return contexts, response, metrics

    def _store_experiment_result(
        self,
        experiment_id: str,
        variant: str,
        query_id: str,
        metrics: Dict[str, float],
        latency_ms: int
    ):
        """Store experiment result for analysis."""
        try:
            if self.db:
                query = """
                    INSERT INTO experiment_results
                    (experiment_id, variant, query_id, faithfulness,
                     answer_relevance, context_precision, latency_ms, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """
                self.db.execute(query, (
                    experiment_id,
                    variant,
                    query_id,
                    metrics.get("faithfulness"),
                    metrics.get("answer_relevance"),
                    metrics.get("context_precision"),
                    latency_ms
                ))
                self.db.commit()
            else:
                # In-memory fallback
                self._results.append({
                    "experiment_id": experiment_id,
                    "variant": variant,
                    "query_id": query_id,
                    "metrics": metrics,
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now()
                })
        except Exception as e:
            logger.error(f"Failed to store experiment result: {e}")

    def _query_default(self, question: str, query_id: str) -> Dict[str, Any]:
        """Execute query with default config (no experiment)."""
        if not self.base_retriever or not self.base_llm:
            logger.warning("⚠️ Skipping API calls (no retriever/LLM configured)")
            return {
                "response": f"Simulated response for: {question}",
                "contexts": ["Context 1", "Context 2"],
                "metrics": {
                    "faithfulness": 0.82,
                    "answer_relevance": 0.78,
                    "context_precision": 0.85
                },
                "variant": "default",
                "experiment_id": None
            }

        contexts = self.base_retriever.retrieve(question)
        response = self.base_llm.generate(question, contexts)
        metrics = self.ragas_evaluator.evaluate(question, contexts, response)

        return {
            "response": response,
            "contexts": contexts,
            "metrics": metrics,
            "variant": "default",
            "experiment_id": None
        }


@dataclass
class ExperimentResults:
    """Results of an A/B test analysis."""
    experiment_id: str
    control_mean: float
    treatment_mean: float
    difference: float
    percent_change: float
    p_value: float
    is_significant: bool
    confidence_interval_95: Tuple[float, float]
    sample_size_control: int
    sample_size_treatment: int
    winner: str  # "control", "treatment", "inconclusive"
    recommendation: str


class StatisticalAnalyzer:
    """Analyzes A/B test results for statistical significance."""

    def __init__(self, db_connection=None, significance_level: float = 0.05):
        """
        Initialize statistical analyzer.

        Args:
            db_connection: Database connection (optional)
            significance_level: p-value threshold for significance
        """
        self.db = db_connection
        self.significance_level = significance_level
        self._in_memory_results = []

    def analyze_experiment(
        self,
        experiment_id: str,
        metric: str = "faithfulness",
        in_memory_data: Optional[List[Dict]] = None
    ) -> ExperimentResults:
        """
        Perform statistical analysis on experiment results.

        Args:
            experiment_id: Experiment to analyze
            metric: Which RAGAS metric to analyze
            in_memory_data: Optional in-memory data for demo mode

        Returns:
            ExperimentResults with significance test results
        """
        try:
            # Fetch results from database or use in-memory data
            control_data = self._get_metric_data(experiment_id, "control", metric, in_memory_data)
            treatment_data = self._get_metric_data(experiment_id, "treatment", metric, in_memory_data)

            if len(control_data) == 0 or len(treatment_data) == 0:
                logger.warning(f"No data for experiment {experiment_id}")
                return self._empty_results(experiment_id)

            # Calculate descriptive statistics
            control_mean = float(np.mean(control_data))
            treatment_mean = float(np.mean(treatment_data))
            difference = treatment_mean - control_mean
            percent_change = (difference / control_mean) * 100 if control_mean != 0 else 0

            # Perform t-test for independent samples
            # Using Welch's t-test (doesn't assume equal variances)
            t_statistic, p_value = stats.ttest_ind(
                treatment_data,
                control_data,
                equal_var=False  # Welch's t-test
            )

            # Calculate 95% confidence interval for the difference
            ci_lower, ci_upper = self._bootstrap_confidence_interval(
                control_data,
                treatment_data
            )

            # Determine significance
            is_significant = p_value < self.significance_level

            # Determine winner
            if not is_significant:
                winner = "inconclusive"
            elif difference > 0:
                winner = "treatment"
            else:
                winner = "control"

            # Generate recommendation
            recommendation = self._generate_recommendation(
                winner=winner,
                difference=difference,
                p_value=float(p_value),
                sample_size_control=len(control_data),
                sample_size_treatment=len(treatment_data)
            )

            logger.info(f"Analysis: {winner}, p={p_value:.4f}, diff={difference:.4f}")

            return ExperimentResults(
                experiment_id=experiment_id,
                control_mean=control_mean,
                treatment_mean=treatment_mean,
                difference=difference,
                percent_change=percent_change,
                p_value=float(p_value),
                is_significant=is_significant,
                confidence_interval_95=(float(ci_lower), float(ci_upper)),
                sample_size_control=len(control_data),
                sample_size_treatment=len(treatment_data),
                winner=winner,
                recommendation=recommendation
            )
        except Exception as e:
            logger.error(f"Failed to analyze experiment: {e}")
            return self._empty_results(experiment_id)

    def _empty_results(self, experiment_id: str) -> ExperimentResults:
        """Return empty results for error cases."""
        return ExperimentResults(
            experiment_id=experiment_id,
            control_mean=0.0,
            treatment_mean=0.0,
            difference=0.0,
            percent_change=0.0,
            p_value=1.0,
            is_significant=False,
            confidence_interval_95=(0.0, 0.0),
            sample_size_control=0,
            sample_size_treatment=0,
            winner="inconclusive",
            recommendation="No data available"
        )

    def _get_metric_data(
        self,
        experiment_id: str,
        variant: str,
        metric: str,
        in_memory_data: Optional[List[Dict]] = None
    ) -> np.ndarray:
        """Fetch metric data for a variant from database or memory."""
        try:
            if self.db:
                query = f"""
                    SELECT {metric}
                    FROM experiment_results
                    WHERE experiment_id = %s AND variant = %s
                    AND {metric} IS NOT NULL
                """
                results = self.db.execute(query, (experiment_id, variant)).fetchall()
                return np.array([r[0] for r in results])
            else:
                # In-memory fallback
                data_source = in_memory_data if in_memory_data else self._in_memory_results
                values = [
                    r["metrics"].get(metric, 0)
                    for r in data_source
                    if r.get("experiment_id") == experiment_id and r.get("variant") == variant
                ]
                return np.array(values) if values else np.array([])
        except Exception as e:
            logger.error(f"Failed to get metric data: {e}")
            return np.array([])

    def _bootstrap_confidence_interval(
        self,
        control_data: np.ndarray,
        treatment_data: np.ndarray,
        n_bootstrap: int = 1000,  # Reduced for performance
        ci_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval using bootstrap resampling.

        More robust than parametric methods for non-normal distributions.
        """
        if len(control_data) == 0 or len(treatment_data) == 0:
            return (0.0, 0.0)

        differences = []

        for _ in range(n_bootstrap):
            # Resample with replacement
            control_sample = np.random.choice(
                control_data,
                size=len(control_data),
                replace=True
            )
            treatment_sample = np.random.choice(
                treatment_data,
                size=len(treatment_data),
                replace=True
            )

            # Calculate difference in means
            diff = np.mean(treatment_sample) - np.mean(control_sample)
            differences.append(diff)

        # Calculate percentiles for CI
        alpha = 1 - ci_level
        lower = float(np.percentile(differences, (alpha/2) * 100))
        upper = float(np.percentile(differences, (1 - alpha/2) * 100))

        return (lower, upper)

    def _generate_recommendation(
        self,
        winner: str,
        difference: float,
        p_value: float,
        sample_size_control: int,
        sample_size_treatment: int
    ) -> str:
        """Generate actionable recommendation based on results."""
        min_sample_size = 1000  # Minimum recommended per variant

        # Check sample size first
        if sample_size_control < min_sample_size or sample_size_treatment < min_sample_size:
            return (
                f"⏳ Keep running. Need {min_sample_size} samples per variant. "
                f"Currently: Control={sample_size_control}, Treatment={sample_size_treatment}"
            )

        # Check for significance
        if winner == "inconclusive":
            return (
                f"⚖️  No significant difference detected (p={p_value:.4f}). "
                f"Either keep running or stick with control to avoid unnecessary changes."
            )

        # Significant result
        if winner == "treatment":
            return (
                f"✅ Roll out treatment! Statistically significant improvement "
                f"of {difference:.4f} ({abs(difference*100):.1f}% increase, p={p_value:.4f}). "
                f"Recommend gradual rollout: 10% → 50% → 100%."
            )
        else:  # winner == "control"
            return (
                f"❌ Keep control. Treatment performed worse "
                f"({difference:.4f}, p={p_value:.4f}). Abandon treatment or iterate."
            )


class RolloutController:
    """Manages gradual rollout of winning variants."""

    def __init__(self, db_connection=None):
        """
        Initialize rollout controller.

        Args:
            db_connection: Database connection (optional)
        """
        self.db = db_connection
        self._rollout_schedules = {}

    def create_rollout_schedule(
        self,
        experiment_id: str,
        stages: List[Tuple[float, timedelta]]
    ) -> Dict[str, Any]:
        """
        Create a gradual rollout schedule.

        Args:
            experiment_id: Experiment to roll out
            stages: List of (traffic_percentage, duration) tuples
                    e.g., [(0.1, timedelta(days=1)), (0.5, timedelta(days=2))]

        Returns:
            Rollout schedule configuration
        """
        schedule = {
            "experiment_id": experiment_id,
            "stages": stages,
            "current_stage": 0,
            "started_at": datetime.now()
        }

        self._rollout_schedules[experiment_id] = schedule
        logger.info(f"Created rollout schedule for {experiment_id}: {len(stages)} stages")

        return schedule

    def check_and_advance(self, experiment_id: str) -> Optional[float]:
        """
        Check if it's time to advance to next rollout stage.

        Args:
            experiment_id: Experiment to check

        Returns:
            New traffic split if advanced, None otherwise
        """
        if experiment_id not in self._rollout_schedules:
            logger.warning(f"No rollout schedule for {experiment_id}")
            return None

        schedule = self._rollout_schedules[experiment_id]
        current_stage = schedule["current_stage"]

        if current_stage >= len(schedule["stages"]):
            logger.info(f"Rollout complete for {experiment_id}")
            return None

        # Check if enough time has passed
        stage_traffic, stage_duration = schedule["stages"][current_stage]
        elapsed = datetime.now() - schedule["started_at"]

        if elapsed >= stage_duration:
            # Advance to next stage
            new_stage = current_stage + 1
            schedule["current_stage"] = new_stage

            if new_stage < len(schedule["stages"]):
                new_traffic, _ = schedule["stages"][new_stage]
                logger.info(f"Advanced {experiment_id} to stage {new_stage}: {new_traffic*100}%")
                return new_traffic
            else:
                logger.info(f"Completed rollout for {experiment_id}")
                return 1.0

        return None


def calculate_required_sample_size(
    effect_size: float,
    alpha: float = 0.05,
    power: float = 0.8,
    std_dev: float = 0.1
) -> int:
    """
    Calculate required sample size for A/B test.

    Args:
        effect_size: Expected difference (e.g., 0.03 for 3% improvement)
        alpha: Significance level (default 0.05)
        power: Statistical power (default 0.8 = 80%)
        std_dev: Assumed standard deviation of metric

    Returns:
        Required sample size per variant
    """
    try:
        from statsmodels.stats.power import tt_solve_power

        # Convert effect size to Cohen's d
        cohens_d = effect_size / std_dev

        n = tt_solve_power(
            effect_size=cohens_d,
            alpha=alpha,
            power=power,
            alternative='two-sided'
        )

        return int(np.ceil(n))
    except ImportError:
        logger.warning("statsmodels not available, using approximation")
        # Simple approximation
        z_alpha = 1.96  # For alpha=0.05
        z_beta = 0.84   # For power=0.8
        cohens_d = effect_size / std_dev
        n = ((z_alpha + z_beta) / cohens_d) ** 2 * 2
        return int(np.ceil(n))


if __name__ == "__main__":
    # CLI Usage Examples
    print("=" * 60)
    print("Module 8.2: A/B Testing for RAG Improvements")
    print("=" * 60)

    # Example 1: Create experiment
    print("\n1. Creating experiment...")
    config = ExperimentConfig(
        experiment_id="exp_chunk_size_001",
        name="Test Chunk Size 1024",
        description="Testing if larger chunks improve faithfulness",
        control_config={"chunk_size": 512, "overlap": 50, "top_k": 5},
        treatment_config={"chunk_size": 1024, "overlap": 100, "top_k": 5},
        traffic_split=0.5
    )

    manager = ExperimentManager()
    exp_id = manager.create_experiment(config)
    print(f"   Created: {exp_id}")

    # Example 2: Traffic splitting
    print("\n2. Testing traffic split...")
    splitter = TrafficSplitter()
    assignments = {"control": 0, "treatment": 0}

    for i in range(100):
        variant = splitter.assign_variant(f"user_{i}", exp_id, 0.5)
        assignments[variant] += 1

    print(f"   Distribution: Control={assignments['control']}, Treatment={assignments['treatment']}")

    # Example 3: Simulate experiment
    print("\n3. Simulating experiment results...")
    pipeline = ABTestingRAGPipeline()

    for i in range(10):
        result = pipeline.query(
            question="What are GDPR requirements?",
            user_id=f"user_{i}",
            query_id=f"query_{i}"
        )
        print(f"   Query {i}: {result['variant']} - Faithfulness: {result['metrics']['faithfulness']:.3f}")

    # Example 4: Statistical analysis
    print("\n4. Analyzing results...")
    # Expected: Limited data, will show "keep running" recommendation

    print("\n✅ Demo complete! See notebook for full walkthrough.")
    print("⚠️  Note: This demo runs without database - use notebook for full implementation.")
