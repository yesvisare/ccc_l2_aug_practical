"""
Module 8.1: RAGAS Evaluation Framework
=====================================

Systematic evaluation of RAG systems using RAGAS (RAG Assessment Framework).
Provides four complementary metrics: faithfulness, answer relevancy, context precision, and context recall.

Key Features:
- Golden test set creation and management with versioning
- RAGAS metric evaluation using LLM-as-judge
- Automated evaluation pipelines with regression detection
- Batched processing with checkpoint recovery
- Domain-specific threshold evaluation
- Cost estimation and tracking

Author: Generated from Video M8.1 Script
Level: 2 (Advanced RAG Systems)
"""

import hashlib
import json
import logging
import pickle
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GoldenSetManager:
    """
    Manages creation, validation, and versioning of golden test sets.

    A golden test set is a curated collection of questions with ground truth answers
    and expected retrieved contexts, used for systematic RAG evaluation.

    Attributes:
        storage_path (Path): Directory where golden sets are stored
    """

    def __init__(self, storage_path: str = "./golden_sets"):
        """
        Initialize GoldenSetManager.

        Args:
            storage_path: Directory path for storing golden sets
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Golden set storage: {self.storage_path}")

    def create_question(
        self,
        question: str,
        ground_truth: str,
        contexts: List[str],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a validated golden set entry.

        Args:
            question: The user query to evaluate
            ground_truth: Expected correct answer
            contexts: List of relevant context chunks that should be retrieved
            metadata: Optional metadata (category, complexity, industries, etc.)

        Returns:
            Dict: Validated golden set entry with generated ID

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        if not question or not ground_truth:
            raise ValueError("Question and ground truth are required")

        if not contexts or len(contexts) < 1:
            raise ValueError("At least one context chunk required")

        # Create entry with stable ID
        entry = {
            "question_id": self._generate_id(question),
            "question": question.strip(),
            "ground_truth": ground_truth.strip(),
            "contexts": [c.strip() for c in contexts],
            "metadata": metadata or {}
        }

        return entry

    def _generate_id(self, question: str) -> str:
        """Generate stable ID from question text using MD5 hash."""
        return hashlib.md5(question.encode()).hexdigest()[:12]

    def save_golden_set(
        self,
        questions: List[Dict],
        name: str,
        version: str = "v1"
    ) -> Path:
        """
        Save golden set with versioning.

        Args:
            questions: List of golden set entries
            name: Name identifier for the golden set
            version: Version string (default: "v1")

        Returns:
            Path: Filepath where golden set was saved

        Raises:
            ValueError: If validation fails
        """
        # Validate set
        self._validate_set(questions)

        # Create metadata
        metadata = {
            "name": name,
            "version": version,
            "count": len(questions),
            "created_at": datetime.now().isoformat(),
            "question_ids": [q["question_id"] for q in questions]
        }

        # Save
        filename = f"{name}_{version}.json"
        filepath = self.storage_path / filename

        with open(filepath, 'w') as f:
            json.dump({
                "metadata": metadata,
                "questions": questions
            }, f, indent=2)

        logger.info(f"✅ Saved {len(questions)} questions to {filepath}")
        return filepath

    def _validate_set(self, questions: List[Dict]) -> None:
        """
        Validate golden set quality.

        Args:
            questions: List of golden set entries

        Raises:
            ValueError: If critical validation fails
        """
        if len(questions) < 20:
            logger.warning(
                f"⚠️  Golden set has {len(questions)} questions. "
                "Minimum 100 recommended for statistical significance."
            )

        # Check for duplicates
        question_texts = [q["question"] for q in questions]
        if len(question_texts) != len(set(question_texts)):
            raise ValueError("Duplicate questions found in set")

        # Calculate and log statistics
        avg_question_len = sum(len(q["question"]) for q in questions) / len(questions)
        avg_answer_len = sum(len(q["ground_truth"]) for q in questions) / len(questions)
        avg_contexts = sum(len(q["contexts"]) for q in questions) / len(questions)

        logger.info(f"📊 Golden Set Statistics:")
        logger.info(f"   Total questions: {len(questions)}")
        logger.info(f"   Avg question length: {avg_question_len:.0f} chars")
        logger.info(f"   Avg answer length: {avg_answer_len:.0f} chars")
        logger.info(f"   Avg contexts per question: {avg_contexts:.1f}")

    def load_golden_set(self, name: str, version: str = "v1") -> List[Dict]:
        """
        Load golden set by name and version.

        Args:
            name: Golden set name identifier
            version: Version string (default: "v1")

        Returns:
            List[Dict]: List of golden set entries

        Raises:
            FileNotFoundError: If golden set file doesn't exist
        """
        filename = f"{name}_{version}.json"
        filepath = self.storage_path / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Golden set not found: {filepath}")

        with open(filepath, 'r') as f:
            data = json.load(f)

        logger.info(f"✅ Loaded {len(data['questions'])} questions from {filepath}")
        return data['questions']


class RAGASEvaluator:
    """
    Evaluates RAG system using RAGAS framework with LLM-as-judge.

    RAGAS provides four complementary metrics:
    - Faithfulness: Is answer grounded in retrieved context?
    - Answer Relevancy: Does answer address the question?
    - Context Precision: Are relevant chunks ranked highest?
    - Context Recall: Did we retrieve all necessary information?

    Attributes:
        model_name (str): OpenAI model for LLM-as-judge evaluation
    """

    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        """
        Initialize RAGASEvaluator.

        Args:
            model_name: OpenAI model name (gpt-3.5-turbo or gpt-4)
                       gpt-3.5-turbo: ~$0.02 per 100 questions
                       gpt-4: ~$0.30 per 100 questions
        """
        self.model_name = model_name
        logger.info(f"RAGAS Evaluator initialized with model: {model_name}")

    def evaluate_system(
        self,
        questions: List[str],
        generated_answers: List[str],
        retrieved_contexts: List[List[str]],
        ground_truths: List[str],
        skip_if_no_key: bool = True
    ) -> Dict:
        """
        Evaluate RAG system using RAGAS metrics.

        Args:
            questions: List of user queries
            generated_answers: List of RAG system's responses
            retrieved_contexts: List of lists of retrieved chunks (per question)
            ground_truths: List of expected correct answers
            skip_if_no_key: If True, skip evaluation when OpenAI key missing

        Returns:
            Dictionary with scores for each metric and metadata

        Raises:
            ImportError: If ragas package not installed
            ValueError: If input lengths don't match
        """
        # Validate inputs
        if not (len(questions) == len(generated_answers) == len(retrieved_contexts) == len(ground_truths)):
            raise ValueError("All input lists must have the same length")

        # Check for OpenAI API key
        from config import Config
        if not Config.has_openai_key():
            if skip_if_no_key:
                logger.warning("⚠️  Skipping RAGAS evaluation (no OpenAI API key)")
                return self._mock_evaluation_result(len(questions))
            else:
                raise ValueError("OPENAI_API_KEY not configured")

        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall
            )
            from datasets import Dataset
        except ImportError as e:
            logger.error(f"❌ RAGAS dependencies not installed: {e}")
            raise

        # Create RAGAS dataset format
        data = {
            "question": questions,
            "answer": generated_answers,
            "contexts": retrieved_contexts,
            "ground_truth": ground_truths
        }

        dataset = Dataset.from_dict(data)

        # Run evaluation
        logger.info(f"🔍 Evaluating {len(questions)} questions with RAGAS...")
        logger.info(f"⏱️  Estimated time: {len(questions) * 3} seconds")

        start_time = time.time()

        try:
            metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
            result = evaluate(dataset, metrics=metrics)

            elapsed = time.time() - start_time
            estimated_cost = self._estimate_cost(len(questions))

            logger.info(f"✅ Evaluation complete in {elapsed:.1f}s")
            logger.info(f"💰 Approximate cost: ${estimated_cost:.2f}")

            # Extract scores from result
            scores = {
                "faithfulness": float(result["faithfulness"]),
                "answer_relevancy": float(result["answer_relevancy"]),
                "context_precision": float(result["context_precision"]),
                "context_recall": float(result["context_recall"])
            }

            return {
                "scores": scores,
                "evaluation_time": elapsed,
                "question_count": len(questions),
                "estimated_cost": estimated_cost
            }

        except Exception as e:
            logger.error(f"❌ Evaluation failed: {str(e)}")
            raise

    def _estimate_cost(self, num_questions: int) -> float:
        """
        Estimate OpenAI API cost for evaluation.

        Args:
            num_questions: Number of questions to evaluate

        Returns:
            Estimated cost in USD
        """
        if "gpt-4" in self.model_name:
            return num_questions * 0.003  # ~$0.30 per 100 questions
        else:
            return num_questions * 0.0002  # ~$0.02 per 100 questions

    def _mock_evaluation_result(self, question_count: int) -> Dict:
        """Return mock evaluation result when API key is missing."""
        return {
            "scores": {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0
            },
            "evaluation_time": 0.0,
            "question_count": question_count,
            "estimated_cost": 0.0,
            "skipped": True,
            "reason": "No OpenAI API key configured"
        }

    def generate_report(self, results: Dict) -> str:
        """
        Generate human-readable evaluation report.

        Args:
            results: Evaluation results from evaluate_system()

        Returns:
            Formatted report string
        """
        if results.get("skipped"):
            return f"\n⚠️  Evaluation skipped: {results.get('reason')}\n"

        scores = results["scores"]

        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("RAGAS EVALUATION REPORT")
        lines.append("=" * 60)
        lines.append(f"\nQuestions Evaluated: {results['question_count']}")
        lines.append(f"Evaluation Time: {results['evaluation_time']:.1f}s")
        lines.append(f"Estimated Cost: ${results['estimated_cost']:.2f}")
        lines.append("\nMetric Scores (0-1 scale, higher is better):")
        lines.append(f"  Faithfulness:      {scores['faithfulness']:.3f}")
        lines.append(f"  Answer Relevancy:  {scores['answer_relevancy']:.3f}")
        lines.append(f"  Context Precision: {scores['context_precision']:.3f}")
        lines.append(f"  Context Recall:    {scores['context_recall']:.3f}")

        overall = self._calculate_overall(scores)
        lines.append(f"\nOverall Score: {overall:.3f}")

        # Interpretation
        lines.append("\n" + "-" * 60)
        lines.append("INTERPRETATION:")
        lines.append(self._interpret_scores(scores))
        lines.append("=" * 60 + "\n")

        return "\n".join(lines)

    def _calculate_overall(self, scores: Dict) -> float:
        """Calculate weighted overall score (faithfulness weighted highest)."""
        weights = {
            'faithfulness': 0.4,
            'answer_relevancy': 0.25,
            'context_precision': 0.2,
            'context_recall': 0.15
        }
        return sum(scores[metric] * weight for metric, weight in weights.items())

    def _interpret_scores(self, scores: Dict) -> str:
        """Provide actionable interpretation of scores."""
        issues = []

        if scores['faithfulness'] < 0.7:
            issues.append(
                "⚠️  LOW FAITHFULNESS (<0.7): System is hallucinating. "
                "Review prompt instructions and consider adding 'only use provided context' constraint."
            )

        if scores['answer_relevancy'] < 0.7:
            issues.append(
                "⚠️  LOW ANSWER RELEVANCY (<0.7): Responses are tangential. "
                "Review system message and ensure query understanding is accurate."
            )

        if scores['context_precision'] < 0.7:
            issues.append(
                "⚠️  LOW CONTEXT PRECISION (<0.7): Irrelevant chunks ranking high. "
                "Check hybrid search alpha, reranking logic, or try pure vector search."
            )

        if scores['context_recall'] < 0.7:
            issues.append(
                "⚠️  LOW CONTEXT RECALL (<0.7): Missing key information. "
                "Review indexing strategy, check for document gaps, or adjust retrieval k value."
            )

        if not issues:
            return "✅ All metrics above 0.7 threshold. System performing well."

        return "\n".join(issues)


class DomainAwareEvaluator:
    """
    Evaluate RAGAS scores with domain-specific thresholds.

    Different domains have different criticality requirements:
    - Compliance: High faithfulness required (no hallucinations)
    - Customer Support: High relevancy required (must be on-point)
    - General: Balanced thresholds
    """

    def __init__(self, domain: str = "general"):
        """
        Initialize domain-aware evaluator.

        Args:
            domain: Domain type (compliance, customer_support, general)
        """
        self.domain = domain
        self.thresholds = self._get_domain_thresholds(domain)
        logger.info(f"Domain-aware evaluator: {domain}")

    def _get_domain_thresholds(self, domain: str) -> Dict[str, float]:
        """Set thresholds based on domain criticality."""
        thresholds = {
            "compliance": {
                "faithfulness": 0.90,  # No hallucinations acceptable
                "answer_relevancy": 0.75,  # Can be verbose
                "context_precision": 0.70,  # Ranking less critical
                "context_recall": 0.80  # Must find all relevant info
            },
            "customer_support": {
                "faithfulness": 0.75,  # Some creativity OK
                "answer_relevancy": 0.85,  # Must be on-point
                "context_precision": 0.65,
                "context_recall": 0.70
            },
            "general": {
                "faithfulness": 0.70,
                "answer_relevancy": 0.70,
                "context_precision": 0.70,
                "context_recall": 0.70
            }
        }
        return thresholds.get(domain, thresholds["general"])

    def evaluate_with_thresholds(self, scores: Dict) -> Dict:
        """
        Evaluate scores against domain thresholds.

        Args:
            scores: RAGAS metric scores

        Returns:
            Dict with pass/fail for each metric and overall assessment
        """
        results = {}
        failures = []

        for metric, score in scores.items():
            threshold = self.thresholds.get(metric, 0.70)
            passed = score >= threshold
            results[metric] = {
                "score": score,
                "threshold": threshold,
                "passed": passed,
                "margin": score - threshold
            }

            if not passed:
                severity = self._calculate_severity(score, threshold)
                failures.append({
                    "metric": metric,
                    "score": score,
                    "threshold": threshold,
                    "severity": severity
                })

        results["overall_passed"] = len(failures) == 0
        results["failures"] = failures

        return results

    def _calculate_severity(self, score: float, threshold: float) -> str:
        """Calculate failure severity based on gap from threshold."""
        gap = threshold - score
        if gap > 0.20:
            return "critical"  # 20%+ below threshold
        elif gap > 0.10:
            return "high"
        elif gap > 0.05:
            return "medium"
        else:
            return "low"


class ResilientEvaluator:
    """
    RAGAS evaluator with batching and checkpointing for large test sets.

    Handles:
    - Batch processing to avoid timeouts
    - Checkpoint recovery to resume from failures
    - Rate limiting to avoid API limits
    - Progress tracking
    """

    def __init__(self, batch_size: int = 20, checkpoint_dir: str = "./checkpoints"):
        """
        Initialize resilient evaluator.

        Args:
            batch_size: Number of questions per batch
            checkpoint_dir: Directory for checkpoint storage
        """
        self.batch_size = batch_size
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = RAGASEvaluator()
        logger.info(f"Resilient evaluator: batch_size={batch_size}")

    def evaluate_with_batching(
        self,
        questions: List[str],
        generated_answers: List[str],
        retrieved_contexts: List[List[str]],
        ground_truths: List[str],
        checkpoint_name: str = "eval"
    ) -> Dict:
        """
        Evaluate in batches with checkpoint recovery.

        Args:
            questions: List of queries
            generated_answers: List of answers
            retrieved_contexts: List of context lists
            ground_truths: List of ground truths
            checkpoint_name: Name for checkpoint file

        Returns:
            Aggregated evaluation results
        """
        total = len(questions)
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_name}.pkl"

        # Try to resume from checkpoint
        if checkpoint_file.exists():
            logger.info(f"📂 Found checkpoint: {checkpoint_file}")
            with open(checkpoint_file, 'rb') as f:
                progress = pickle.load(f)
            logger.info(f"   Resuming from question {progress['completed']}/{total}")
        else:
            progress = {
                "completed": 0,
                "results": [],
                "failed_batches": []
            }

        # Process in batches
        for start_idx in range(progress["completed"], total, self.batch_size):
            end_idx = min(start_idx + self.batch_size, total)
            batch_num = start_idx // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            logger.info(f"\n📦 Processing batch {batch_num}/{total_batches} (questions {start_idx}-{end_idx})")

            try:
                # Evaluate batch
                batch_result = self.evaluator.evaluate_system(
                    questions=questions[start_idx:end_idx],
                    generated_answers=generated_answers[start_idx:end_idx],
                    retrieved_contexts=retrieved_contexts[start_idx:end_idx],
                    ground_truths=ground_truths[start_idx:end_idx]
                )

                progress["results"].append(batch_result)
                progress["completed"] = end_idx
                logger.info("✅ Batch complete")

            except Exception as e:
                logger.error(f"❌ Batch failed: {str(e)}")
                progress["failed_batches"].append({
                    "range": f"{start_idx}-{end_idx}",
                    "error": str(e)
                })
                progress["completed"] = end_idx

            # Save checkpoint after each batch
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(progress, f)
            logger.info("💾 Checkpoint saved")

            # Rate limit protection
            time.sleep(2)  # 2 second delay between batches

        # Aggregate results
        aggregated = self._aggregate_batch_results(progress["results"])

        logger.info(f"\n✅ Evaluation complete!")
        logger.info(f"   Total questions: {total}")
        logger.info(f"   Successful batches: {len(progress['results'])}")
        logger.info(f"   Failed batches: {len(progress['failed_batches'])}")

        # Clean up checkpoint on success
        if checkpoint_file.exists():
            checkpoint_file.unlink()

        return aggregated

    def _aggregate_batch_results(self, batch_results: List[Dict]) -> Dict:
        """Aggregate results from multiple batches."""
        if not batch_results:
            return {}

        # Calculate average scores across batches
        total_questions = sum(r["question_count"] for r in batch_results)

        aggregated_scores = {}
        for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            weighted_sum = sum(
                r["scores"][metric] * r["question_count"]
                for r in batch_results
            )
            aggregated_scores[metric] = weighted_sum / total_questions

        total_time = sum(r["evaluation_time"] for r in batch_results)
        total_cost = sum(r["estimated_cost"] for r in batch_results)

        return {
            "scores": aggregated_scores,
            "evaluation_time": total_time,
            "question_count": total_questions,
            "estimated_cost": total_cost
        }


class EvaluationPipeline:
    """
    Automated pipeline for nightly RAG evaluation with regression detection.

    Features:
    - Load golden test sets
    - Generate RAG responses
    - Evaluate with RAGAS
    - Detect regressions vs. baseline
    - Save results with timestamps
    - Update baselines
    """

    def __init__(
        self,
        results_dir: str = "./evaluation_results",
        baseline_file: str = "baseline.json"
    ):
        """
        Initialize evaluation pipeline.

        Args:
            results_dir: Directory for storing evaluation results
            baseline_file: Filename for baseline scores
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_file = self.results_dir / baseline_file
        self.baseline = self._load_baseline()
        logger.info(f"Evaluation pipeline initialized")

    def run_pipeline(
        self,
        golden_set_name: str,
        golden_set_version: str,
        rag_query_func,
        save_results: bool = True
    ) -> Dict:
        """
        Run complete evaluation pipeline.

        Args:
            golden_set_name: Name of golden test set
            golden_set_version: Version of golden test set
            rag_query_func: Function that takes a question and returns
                          {"answer": str, "contexts": List[str]}
            save_results: Whether to save results to disk

        Returns:
            Dictionary with results and regression analysis
        """
        logger.info("\n" + "=" * 60)
        logger.info("RAGAS EVALUATION PIPELINE")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"Golden Set: {golden_set_name} {golden_set_version}")
        logger.info("=" * 60 + "\n")

        # Step 1: Load golden set
        manager = GoldenSetManager()
        golden_questions = manager.load_golden_set(golden_set_name, golden_set_version)
        logger.info(f"✅ Loaded {len(golden_questions)} test questions\n")

        # Step 2: Generate responses
        logger.info("🤖 Generating RAG responses...")
        questions = []
        generated_answers = []
        retrieved_contexts = []
        ground_truths = []

        for i, item in enumerate(golden_questions):
            try:
                response = rag_query_func(item["question"])
                questions.append(item["question"])
                generated_answers.append(response["answer"])
                retrieved_contexts.append(response["contexts"])
                ground_truths.append(item["ground_truth"])

                if (i + 1) % 10 == 0:
                    logger.info(f"  Processed {i + 1}/{len(golden_questions)} questions")

            except Exception as e:
                logger.error(f"  ❌ Error on question {i}: {str(e)}")
                continue

        logger.info(f"✅ Generated {len(generated_answers)} responses\n")

        # Step 3: Evaluate with RAGAS
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate_system(
            questions=questions,
            generated_answers=generated_answers,
            retrieved_contexts=retrieved_contexts,
            ground_truths=ground_truths
        )

        # Step 4: Regression analysis
        regression_analysis = self._check_for_regressions(results["scores"])

        # Step 5: Save results
        if save_results:
            self._save_results(
                results=results,
                regression_analysis=regression_analysis,
                golden_set_name=golden_set_name
            )

        # Step 6: Print report
        self._print_pipeline_report(results, regression_analysis)

        return {
            "results": results,
            "regression_analysis": regression_analysis
        }

    def _check_for_regressions(self, current_scores: Dict) -> Dict:
        """Compare current scores to baseline and detect regressions."""
        if not self.baseline:
            logger.info("📊 No baseline found. Current scores will become baseline.")
            return {
                "has_regression": False,
                "is_first_run": True,
                "message": "First evaluation - establishing baseline"
            }

        # Calculate deltas
        deltas = {}
        regressions = []
        improvements = []

        for metric, current_value in current_scores.items():
            baseline_value = self.baseline.get(metric, 0)
            delta = current_value - baseline_value
            deltas[metric] = {
                "current": current_value,
                "baseline": baseline_value,
                "delta": delta,
                "percent_change": (delta / baseline_value * 100) if baseline_value > 0 else 0
            }

            # Flag regression if drop > 5%
            if delta < -0.05:
                regressions.append({
                    "metric": metric,
                    "delta": delta,
                    "severity": "high" if delta < -0.10 else "medium"
                })

            # Flag improvement if gain > 5%
            elif delta > 0.05:
                improvements.append({
                    "metric": metric,
                    "delta": delta
                })

        return {
            "has_regression": len(regressions) > 0,
            "regressions": regressions,
            "improvements": improvements,
            "deltas": deltas,
            "is_first_run": False
        }

    def _save_results(
        self,
        results: Dict,
        regression_analysis: Dict,
        golden_set_name: str
    ) -> None:
        """Save evaluation results with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eval_{golden_set_name}_{timestamp}.json"
        filepath = self.results_dir / filename

        output = {
            "timestamp": datetime.now().isoformat(),
            "golden_set": golden_set_name,
            "scores": results["scores"],
            "regression_analysis": regression_analysis,
            "metadata": {
                "question_count": results["question_count"],
                "evaluation_time": results["evaluation_time"],
                "estimated_cost": results.get("estimated_cost", 0)
            }
        }

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n💾 Results saved to: {filepath}")

        # Update baseline if this is better or first run
        if regression_analysis["is_first_run"] or not regression_analysis["has_regression"]:
            self._update_baseline(results["scores"])

    def _update_baseline(self, scores: Dict) -> None:
        """Update baseline scores."""
        with open(self.baseline_file, 'w') as f:
            json.dump(scores, f, indent=2)
        logger.info(f"📊 Baseline updated: {self.baseline_file}")
        self.baseline = scores

    def _load_baseline(self) -> Dict:
        """Load baseline scores if they exist."""
        if self.baseline_file.exists():
            with open(self.baseline_file, 'r') as f:
                return json.load(f)
        return {}

    def _print_pipeline_report(self, results: Dict, regression_analysis: Dict) -> None:
        """Print comprehensive pipeline report."""
        scores = results["scores"]

        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE RESULTS")
        logger.info("=" * 60)

        # Current scores
        logger.info("\nCurrent Scores:")
        for metric, score in scores.items():
            logger.info(f"  {metric:20s}: {score:.3f}")

        # Regression analysis
        if regression_analysis["is_first_run"]:
            logger.info("\n📊 First evaluation - baseline established")
        else:
            logger.info("\nRegression Analysis:")

            if regression_analysis["has_regression"]:
                logger.error("\n❌ REGRESSIONS DETECTED:")
                for reg in regression_analysis["regressions"]:
                    logger.error(
                        f"  {reg['metric']}: {reg['delta']:.3f} "
                        f"({reg['severity']} severity)"
                    )
            else:
                logger.info("✅ No regressions detected")

            if regression_analysis["improvements"]:
                logger.info("\n📈 Improvements:")
                for imp in regression_analysis["improvements"]:
                    logger.info(f"  {imp['metric']}: +{imp['delta']:.3f}")

        logger.info("=" * 60 + "\n")


# Utility functions

def create_sample_golden_set() -> Path:
    """
    Create a sample golden test set for demonstration.

    Returns:
        Path to saved golden set file
    """
    manager = GoldenSetManager()

    questions = [
        manager.create_question(
            question="What are the GDPR data retention requirements for employee records?",
            ground_truth="GDPR requires employee records to be retained for 6 years after employment ends, with some exceptions for legal obligations.",
            contexts=[
                "GDPR Article 17 establishes right to erasure but includes exemptions for legal obligations.",
                "Employee records must be retained for 6 years after employment termination under GDPR."
            ],
            metadata={"category": "compliance", "complexity": "medium"}
        ),
        manager.create_question(
            question="What is the maximum GDPR fine?",
            ground_truth="GDPR violations can result in fines up to €20 million or 4% of annual global turnover, whichever is higher.",
            contexts=[
                "GDPR Article 83 establishes maximum fines of €20 million or 4% of global annual turnover.",
                "The actual fine depends on severity, intent, and mitigating factors."
            ],
            metadata={"category": "compliance", "complexity": "low"}
        )
    ]

    return manager.save_golden_set(questions, "sample_set", "v1")


# CLI Usage Example
if __name__ == "__main__":
    """
    Example CLI usage for the RAGAS evaluation framework.
    """
    print("RAGAS Evaluation Framework - Module 8.1")
    print("=" * 60)

    # Example 1: Create sample golden set
    print("\n1. Creating sample golden test set...")
    filepath = create_sample_golden_set()
    print(f"   Created: {filepath}")

    # Example 2: Load and inspect golden set
    print("\n2. Loading golden set...")
    manager = GoldenSetManager()
    questions = manager.load_golden_set("sample_set", "v1")
    print(f"   Loaded {len(questions)} questions")

    # Example 3: Mock evaluation (no actual RAG system)
    print("\n3. Running mock evaluation...")
    print("   Note: This requires OpenAI API key and a working RAG system")
    print("   Skipping actual evaluation in CLI mode")

    # Example 4: Domain-aware evaluation
    print("\n4. Domain-aware threshold evaluation...")
    evaluator = DomainAwareEvaluator(domain="compliance")
    mock_scores = {
        "faithfulness": 0.85,
        "answer_relevancy": 0.78,
        "context_precision": 0.72,
        "context_recall": 0.81
    }
    assessment = evaluator.evaluate_with_thresholds(mock_scores)
    print(f"   Overall passed: {assessment['overall_passed']}")
    if assessment['failures']:
        print("   Failures:")
        for failure in assessment['failures']:
            print(f"     - {failure['metric']}: {failure['severity']} severity")

    print("\n" + "=" * 60)
    print("See README.md for full usage examples and Jupyter notebook walkthrough")
