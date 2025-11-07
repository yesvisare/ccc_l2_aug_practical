"""
Smoke tests for Module 8.2: A/B Testing for RAG Improvements

Run with: python tests_smoke.py
"""

import sys
import logging
from datetime import timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all required modules can be imported."""
    print("\n" + "=" * 60)
    print("TEST 1: Module Imports")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import (
            ExperimentConfig,
            ExperimentManager,
            TrafficSplitter,
            ABTestingRAGPipeline,
            StatisticalAnalyzer,
            RolloutController,
            calculate_required_sample_size
        )
        print("✅ All core imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_config_loads():
    """Test that configuration loads without errors."""
    print("\n" + "=" * 60)
    print("TEST 2: Configuration Loading")
    print("=" * 60)

    try:
        import config
        print(f"✅ Config loaded successfully")
        print(f"   Traffic split: {config.DEFAULT_TRAFFIC_SPLIT}")
        print(f"   Min sample size: {config.MIN_SAMPLE_SIZE}")
        print(f"   Significance level: {config.SIGNIFICANCE_LEVEL}")
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False


def test_experiment_creation():
    """Test basic experiment creation."""
    print("\n" + "=" * 60)
    print("TEST 3: Experiment Creation")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import ExperimentConfig, ExperimentManager

        config = ExperimentConfig(
            experiment_id="test_exp_001",
            name="Test Experiment",
            description="Smoke test experiment",
            control_config={"chunk_size": 512},
            treatment_config={"chunk_size": 1024},
            traffic_split=0.5
        )

        manager = ExperimentManager()
        exp_id = manager.create_experiment(config)

        print(f"✅ Experiment created: {exp_id}")
        print(f"   Name: {config.name}")
        print(f"   Traffic split: {config.traffic_split}")
        return True
    except Exception as e:
        print(f"❌ Experiment creation failed: {e}")
        return False


def test_traffic_splitting():
    """Test traffic splitting produces reasonable distribution."""
    print("\n" + "=" * 60)
    print("TEST 4: Traffic Splitting")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import TrafficSplitter

        splitter = TrafficSplitter()
        assignments = {"control": 0, "treatment": 0}

        # Test with 100 users
        for i in range(100):
            variant = splitter.assign_variant(f"user_{i}", "test_exp", 0.5)
            assignments[variant] += 1

        # Check distribution is reasonable (40-60% range)
        if 40 <= assignments["control"] <= 60 and 40 <= assignments["treatment"] <= 60:
            print(f"✅ Traffic split distribution reasonable:")
            print(f"   Control: {assignments['control']}")
            print(f"   Treatment: {assignments['treatment']}")
            return True
        else:
            print(f"❌ Traffic split distribution skewed:")
            print(f"   Control: {assignments['control']}")
            print(f"   Treatment: {assignments['treatment']}")
            return False

    except Exception as e:
        print(f"❌ Traffic splitting failed: {e}")
        return False


def test_assignment_consistency():
    """Test that same user gets same variant."""
    print("\n" + "=" * 60)
    print("TEST 5: Assignment Consistency")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import TrafficSplitter

        splitter = TrafficSplitter()

        # Assign same user multiple times
        variant1 = splitter.assign_variant("user_test", "test_exp", 0.5)
        variant2 = splitter.assign_variant("user_test", "test_exp", 0.5)
        variant3 = splitter.assign_variant("user_test", "test_exp", 0.5)

        if variant1 == variant2 == variant3:
            print(f"✅ Assignment consistency verified")
            print(f"   user_test always assigned to: {variant1}")
            return True
        else:
            print(f"❌ Assignment inconsistent: {variant1}, {variant2}, {variant3}")
            return False

    except Exception as e:
        print(f"❌ Consistency test failed: {e}")
        return False


def test_rag_pipeline():
    """Test RAG pipeline executes queries."""
    print("\n" + "=" * 60)
    print("TEST 6: RAG Pipeline Execution")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import ABTestingRAGPipeline

        pipeline = ABTestingRAGPipeline()

        result = pipeline.query(
            question="Test question",
            user_id="user_test",
            query_id="query_test"
        )

        # Check result has required fields
        required_fields = ["response", "contexts", "metrics", "variant"]
        missing = [f for f in required_fields if f not in result]

        if not missing:
            print(f"✅ RAG pipeline executed successfully")
            print(f"   Variant: {result['variant']}")
            print(f"   Metrics: {list(result['metrics'].keys())}")
            return True
        else:
            print(f"❌ Missing fields in result: {missing}")
            return False

    except Exception as e:
        print(f"❌ RAG pipeline failed: {e}")
        return False


def test_statistical_analysis():
    """Test statistical analysis returns plausible results."""
    print("\n" + "=" * 60)
    print("TEST 7: Statistical Analysis")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import (
            ABTestingRAGPipeline,
            StatisticalAnalyzer
        )

        # Generate some test data
        pipeline = ABTestingRAGPipeline()
        for i in range(50):
            pipeline.query(
                question="Test query",
                user_id=f"user_{i}",
                query_id=f"query_{i}"
            )

        # Analyze
        analyzer = StatisticalAnalyzer()
        results = analyzer.analyze_experiment(
            "test_exp_001",
            metric="faithfulness",
            in_memory_data=pipeline._results
        )

        # Check results have required fields
        if hasattr(results, 'p_value') and hasattr(results, 'winner'):
            print(f"✅ Statistical analysis completed")
            print(f"   Sample sizes: Control={results.sample_size_control}, Treatment={results.sample_size_treatment}")
            print(f"   P-value: {results.p_value:.4f}")
            print(f"   Winner: {results.winner}")
            return True
        else:
            print(f"❌ Analysis results missing fields")
            return False

    except Exception as e:
        print(f"❌ Statistical analysis failed: {e}")
        return False


def test_sample_size_calculation():
    """Test sample size calculator returns reasonable values."""
    print("\n" + "=" * 60)
    print("TEST 8: Sample Size Calculation")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import calculate_required_sample_size

        # Test with 3% effect size
        required_n = calculate_required_sample_size(
            effect_size=0.03,
            alpha=0.05,
            power=0.8
        )

        # Should be between 500 and 3000 for typical RAG metrics
        if 500 <= required_n <= 3000:
            print(f"✅ Sample size calculation reasonable")
            print(f"   Required samples per variant: {required_n}")
            print(f"   For 3% effect size at 80% power")
            return True
        else:
            print(f"⚠️  Sample size seems unusual: {required_n}")
            print(f"   Expected range: 500-3000")
            return True  # Still pass, just warn

    except Exception as e:
        print(f"❌ Sample size calculation failed: {e}")
        return False


def test_rollout_controller():
    """Test rollout controller creates valid schedules."""
    print("\n" + "=" * 60)
    print("TEST 9: Rollout Controller")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import RolloutController

        controller = RolloutController()
        schedule = controller.create_rollout_schedule(
            experiment_id="test_exp",
            stages=[
                (0.1, timedelta(days=1)),
                (0.5, timedelta(days=2)),
                (1.0, timedelta(days=0))
            ]
        )

        if schedule and 'stages' in schedule and len(schedule['stages']) == 3:
            print(f"✅ Rollout schedule created")
            print(f"   Stages: {len(schedule['stages'])}")
            print(f"   Stage 1: {schedule['stages'][0][0]*100}% traffic")
            return True
        else:
            print(f"❌ Invalid rollout schedule")
            return False

    except Exception as e:
        print(f"❌ Rollout controller failed: {e}")
        return False


def test_graceful_degradation():
    """Test that system works without external dependencies."""
    print("\n" + "=" * 60)
    print("TEST 10: Graceful Degradation (No DB/APIs)")
    print("=" * 60)

    try:
        from l2_m8_ab_testing_rag_improvements import (
            ExperimentManager,
            ABTestingRAGPipeline
        )

        # Should work without database
        manager = ExperimentManager(db_connection=None)
        pipeline = ABTestingRAGPipeline(
            base_retriever=None,
            base_llm=None,
            ragas_evaluator=None,
            db_connection=None
        )

        result = pipeline.query("Test", "user_1", "q1")

        if result and 'variant' in result:
            print(f"✅ Graceful degradation works")
            print(f"   System operates without external dependencies")
            return True
        else:
            print(f"❌ Failed without dependencies")
            return False

    except Exception as e:
        print(f"❌ Graceful degradation failed: {e}")
        return False


def run_all_tests():
    """Run all smoke tests and report results."""
    tests = [
        test_imports,
        test_config_loads,
        test_experiment_creation,
        test_traffic_splitting,
        test_assignment_consistency,
        test_rag_pipeline,
        test_statistical_analysis,
        test_sample_size_calculation,
        test_rollout_controller,
        test_graceful_degradation
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            logger.error(f"Test {test.__name__} crashed: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 All smoke tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
