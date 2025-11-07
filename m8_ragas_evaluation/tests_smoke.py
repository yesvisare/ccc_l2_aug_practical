"""
Smoke tests for RAGAS Evaluation Framework.
Tests basic functionality without requiring API keys or external services.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from l2_m8_ragas_evaluation_framework import (
    GoldenSetManager,
    RAGASEvaluator,
    DomainAwareEvaluator,
    ResilientEvaluator,
    EvaluationPipeline
)
from config import Config


class TestConfig:
    """Test configuration loading and validation."""

    def test_config_has_required_attributes(self):
        """Test that Config has all required attributes."""
        assert hasattr(Config, 'OPENAI_API_KEY')
        assert hasattr(Config, 'OPENAI_MODEL')
        assert hasattr(Config, 'GOLDEN_SET_DIR')
        assert hasattr(Config, 'RESULTS_DIR')
        assert hasattr(Config, 'BATCH_SIZE')

    def test_directories_created(self):
        """Test that required directories are created."""
        assert Config.GOLDEN_SET_DIR.exists()
        assert Config.RESULTS_DIR.exists()

    def test_get_domain_thresholds(self):
        """Test domain thresholds retrieval."""
        thresholds = Config.get_domain_thresholds()
        assert 'faithfulness' in thresholds
        assert 'answer_relevancy' in thresholds
        assert 'context_precision' in thresholds
        assert 'context_recall' in thresholds


class TestGoldenSetManager:
    """Test golden set creation and management."""

    def test_manager_initialization(self, tmp_path):
        """Test GoldenSetManager initialization."""
        manager = GoldenSetManager(storage_path=str(tmp_path))
        assert manager.storage_path.exists()

    def test_create_question(self, tmp_path):
        """Test question creation."""
        manager = GoldenSetManager(storage_path=str(tmp_path))

        question = manager.create_question(
            question="What is RAGAS?",
            ground_truth="RAGAS is RAG Assessment Framework",
            contexts=["RAGAS provides systematic evaluation of RAG systems"],
            metadata={"category": "definition"}
        )

        assert question['question'] == "What is RAGAS?"
        assert question['ground_truth'] == "RAGAS is RAG Assessment Framework"
        assert len(question['contexts']) == 1
        assert 'question_id' in question

    def test_create_question_validation(self, tmp_path):
        """Test question creation validation."""
        manager = GoldenSetManager(storage_path=str(tmp_path))

        # Missing question
        with pytest.raises(ValueError):
            manager.create_question(
                question="",
                ground_truth="Answer",
                contexts=["Context"]
            )

        # Missing contexts
        with pytest.raises(ValueError):
            manager.create_question(
                question="Question",
                ground_truth="Answer",
                contexts=[]
            )

    def test_save_and_load_golden_set(self, tmp_path):
        """Test saving and loading golden sets."""
        manager = GoldenSetManager(storage_path=str(tmp_path))

        questions = [
            manager.create_question(
                question="What is RAGAS?",
                ground_truth="RAG Assessment Framework",
                contexts=["Context 1"]
            ),
            manager.create_question(
                question="How does RAGAS work?",
                ground_truth="Uses LLM-as-judge",
                contexts=["Context 2"]
            )
        ]

        # Save
        filepath = manager.save_golden_set(questions, "test_set", "v1")
        assert filepath.exists()

        # Load
        loaded = manager.load_golden_set("test_set", "v1")
        assert len(loaded) == 2
        assert loaded[0]['question'] == "What is RAGAS?"


class TestRAGASEvaluator:
    """Test RAGAS evaluator functionality."""

    def test_evaluator_initialization(self):
        """Test RAGASEvaluator initialization."""
        evaluator = RAGASEvaluator(model_name="gpt-3.5-turbo")
        assert evaluator.model_name == "gpt-3.5-turbo"

    def test_evaluation_skip_without_key(self):
        """Test that evaluation gracefully skips without API key."""
        evaluator = RAGASEvaluator()

        results = evaluator.evaluate_system(
            questions=["Test question"],
            generated_answers=["Test answer"],
            retrieved_contexts=[["Test context"]],
            ground_truths=["Test truth"],
            skip_if_no_key=True
        )

        # Should return mock result if no key
        if not Config.has_openai_key():
            assert results.get('skipped') is True
            assert 'reason' in results

    def test_cost_estimation(self):
        """Test cost estimation."""
        evaluator = RAGASEvaluator(model_name="gpt-3.5-turbo")
        cost = evaluator._estimate_cost(100)
        assert 0.01 < cost < 0.10  # Should be ~$0.02 for 100 questions

        evaluator_gpt4 = RAGASEvaluator(model_name="gpt-4")
        cost_gpt4 = evaluator_gpt4._estimate_cost(100)
        assert cost_gpt4 > cost  # GPT-4 should be more expensive

    def test_generate_report(self):
        """Test report generation."""
        evaluator = RAGASEvaluator()

        results = {
            "scores": {
                "faithfulness": 0.85,
                "answer_relevancy": 0.78,
                "context_precision": 0.72,
                "context_recall": 0.81
            },
            "evaluation_time": 10.5,
            "question_count": 10,
            "estimated_cost": 0.02
        }

        report = evaluator.generate_report(results)
        assert "RAGAS EVALUATION REPORT" in report
        assert "0.850" in report  # Faithfulness score
        assert "10" in report  # Question count


class TestDomainAwareEvaluator:
    """Test domain-aware evaluation."""

    def test_domain_thresholds(self):
        """Test domain-specific thresholds."""
        # Compliance domain
        compliance = DomainAwareEvaluator(domain="compliance")
        assert compliance.thresholds['faithfulness'] == 0.90

        # General domain
        general = DomainAwareEvaluator(domain="general")
        assert general.thresholds['faithfulness'] == 0.70

        # Customer support domain
        support = DomainAwareEvaluator(domain="customer_support")
        assert support.thresholds['answer_relevancy'] == 0.85

    def test_threshold_evaluation(self):
        """Test evaluation against thresholds."""
        evaluator = DomainAwareEvaluator(domain="compliance")

        # Passing scores
        passing_scores = {
            "faithfulness": 0.92,
            "answer_relevancy": 0.80,
            "context_precision": 0.75,
            "context_recall": 0.85
        }
        result = evaluator.evaluate_with_thresholds(passing_scores)
        assert result['overall_passed'] is True
        assert len(result['failures']) == 0

        # Failing scores
        failing_scores = {
            "faithfulness": 0.65,  # Below 0.90 threshold
            "answer_relevancy": 0.80,
            "context_precision": 0.75,
            "context_recall": 0.85
        }
        result = evaluator.evaluate_with_thresholds(failing_scores)
        assert result['overall_passed'] is False
        assert len(result['failures']) > 0
        assert result['failures'][0]['metric'] == 'faithfulness'


class TestResilientEvaluator:
    """Test resilient evaluation with batching."""

    def test_resilient_evaluator_initialization(self, tmp_path):
        """Test ResilientEvaluator initialization."""
        evaluator = ResilientEvaluator(
            batch_size=10,
            checkpoint_dir=str(tmp_path)
        )
        assert evaluator.batch_size == 10
        assert evaluator.checkpoint_dir.exists()

    def test_batch_result_aggregation(self, tmp_path):
        """Test aggregation of batch results."""
        evaluator = ResilientEvaluator(checkpoint_dir=str(tmp_path))

        batch_results = [
            {
                "scores": {
                    "faithfulness": 0.80,
                    "answer_relevancy": 0.75,
                    "context_precision": 0.70,
                    "context_recall": 0.72
                },
                "question_count": 10,
                "evaluation_time": 30.0,
                "estimated_cost": 0.02
            },
            {
                "scores": {
                    "faithfulness": 0.90,
                    "answer_relevancy": 0.85,
                    "context_precision": 0.80,
                    "context_recall": 0.82
                },
                "question_count": 10,
                "evaluation_time": 30.0,
                "estimated_cost": 0.02
            }
        ]

        aggregated = evaluator._aggregate_batch_results(batch_results)

        assert aggregated['question_count'] == 20
        assert 0.80 < aggregated['scores']['faithfulness'] < 0.90  # Weighted average
        assert aggregated['evaluation_time'] == 60.0
        assert aggregated['estimated_cost'] == 0.04


class TestEvaluationPipeline:
    """Test evaluation pipeline."""

    def test_pipeline_initialization(self, tmp_path):
        """Test EvaluationPipeline initialization."""
        pipeline = EvaluationPipeline(
            results_dir=str(tmp_path / "results")
        )
        assert pipeline.results_dir.exists()

    def test_regression_detection_first_run(self, tmp_path):
        """Test regression detection on first run."""
        pipeline = EvaluationPipeline(results_dir=str(tmp_path))

        scores = {
            "faithfulness": 0.85,
            "answer_relevancy": 0.80,
            "context_precision": 0.75,
            "context_recall": 0.78
        }

        regression = pipeline._check_for_regressions(scores)
        assert regression['is_first_run'] is True
        assert regression['has_regression'] is False

    def test_regression_detection_with_baseline(self, tmp_path):
        """Test regression detection with baseline."""
        pipeline = EvaluationPipeline(results_dir=str(tmp_path))

        # Set baseline
        pipeline.baseline = {
            "faithfulness": 0.85,
            "answer_relevancy": 0.80,
            "context_precision": 0.75,
            "context_recall": 0.78
        }

        # Test regression (drop >5%)
        current_scores = {
            "faithfulness": 0.75,  # Dropped 0.10 (>5%)
            "answer_relevancy": 0.79,
            "context_precision": 0.74,
            "context_recall": 0.77
        }

        regression = pipeline._check_for_regressions(current_scores)
        assert regression['has_regression'] is True
        assert len(regression['regressions']) > 0
        assert regression['regressions'][0]['metric'] == 'faithfulness'


def test_example_data_loads():
    """Test that example_data.json loads correctly."""
    example_file = Path(__file__).parent / "example_data.json"
    assert example_file.exists(), "example_data.json not found"

    import json
    with open(example_file) as f:
        data = json.load(f)

    assert 'metadata' in data
    assert 'questions' in data
    assert len(data['questions']) > 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
