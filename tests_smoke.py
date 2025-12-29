"""
Module 7.2: Application Performance Monitoring - Smoke Tests
Minimal tests to verify basic functionality.

Tests gracefully skip network operations when keys/services are missing.
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO)


def test_config_loads():
    """Test that configuration loads without errors."""
    print("\n" + "="*60)
    print("TEST 1: Configuration Loading")
    print("="*60)

    try:
        from config import apm_config

        assert apm_config is not None, "Config should not be None"
        assert hasattr(apm_config, 'DD_SERVICE'), "Config should have DD_SERVICE"
        assert hasattr(apm_config, 'DD_TRACE_SAMPLE_RATE'), "Config should have DD_TRACE_SAMPLE_RATE"

        print(f"✅ Config loaded successfully")
        print(f"   Service: {apm_config.DD_SERVICE}")
        print(f"   Sample Rate: {apm_config.DD_TRACE_SAMPLE_RATE}")
        print(f"   APM Enabled: {apm_config.is_enabled()}")

        return True

    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False


def test_apm_manager_initializes():
    """Test that APM manager initializes (or gracefully skips if no keys)."""
    print("\n" + "="*60)
    print("TEST 2: APM Manager Initialization")
    print("="*60)

    try:
        from config import apm_config
        from l2_m7_application_performance_monitoring import APMManager

        manager = APMManager(apm_config)
        assert manager is not None, "Manager should not be None"

        # Try initialization (will skip if no keys)
        result = manager.initialize()

        if result:
            print("✅ APM initialized successfully")
            print("   Shutting down...")
            manager.shutdown()
        else:
            print("⚠️  APM initialization skipped (no DD_API_KEY)")
            print("   This is expected if running without Datadog credentials")

        return True

    except Exception as e:
        print(f"❌ APM manager test failed: {e}")
        return False


def test_pipeline_processes_query():
    """Test that pipeline can process a query (without APM if keys missing)."""
    print("\n" + "="*60)
    print("TEST 3: Pipeline Query Processing")
    print("="*60)

    try:
        from l2_m7_application_performance_monitoring import ProfiledRAGPipeline

        # Create pipeline (will work without APM)
        pipeline = ProfiledRAGPipeline(use_apm=False)

        # Process test query
        result = pipeline.process_query(
            query="What are GDPR requirements?",
            user_id="test_user_123"
        )

        # Validate result structure
        assert isinstance(result, dict), "Result should be a dict"
        assert "response" in result, "Result should have 'response' key"
        assert "context_size" in result, "Result should have 'context_size' key"
        assert "num_results" in result, "Result should have 'num_results' key"

        print("✅ Pipeline processed query successfully")
        print(f"   Response length: {len(result['response'])} chars")
        print(f"   Context size: {result['context_size']} chars")
        print(f"   Num results: {result['num_results']}")

        return True

    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_profiler():
    """Test memory profiler functionality."""
    print("\n" + "="*60)
    print("TEST 4: Memory Profiler")
    print("="*60)

    try:
        from l2_m7_application_performance_monitoring import MemoryProfiler

        profiler = MemoryProfiler()

        # Get initial stats
        stats = profiler.get_memory_stats()

        assert isinstance(stats, dict), "Stats should be a dict"
        assert "current_mb" in stats, "Stats should have 'current_mb'"
        assert "peak_mb" in stats, "Stats should have 'peak_mb'"
        assert "baseline_mb" in stats, "Stats should have 'baseline_mb'"
        assert "growth_mb" in stats, "Stats should have 'growth_mb'"

        print("✅ Memory profiler working correctly")
        print(f"   Current: {stats['current_mb']:.2f} MB")
        print(f"   Peak: {stats['peak_mb']:.2f} MB")
        print(f"   Growth: {stats['growth_mb']:.2f} MB")

        return True

    except Exception as e:
        print(f"❌ Memory profiler test failed: {e}")
        return False


def test_query_cache():
    """Test query cache with LRU eviction."""
    print("\n" + "="*60)
    print("TEST 5: Query Cache")
    print("="*60)

    try:
        from l2_m7_application_performance_monitoring import QueryCache

        cache = QueryCache(max_size=5)

        # Add some items
        for i in range(7):
            cache.set(f"query_{i}", "user_1", {"result": f"answer_{i}"})

        # Cache should be limited to 5
        assert len(cache._cache) == 5, f"Cache should have 5 items, got {len(cache._cache)}"

        # Most recent items should be in cache
        result = cache.get("query_6", "user_1")
        assert result is not None, "query_6 should be in cache"

        # Oldest items should be evicted
        result = cache.get("query_0", "user_1")
        assert result is None, "query_0 should be evicted"

        print("✅ Query cache working correctly")
        print(f"   Cache size: {len(cache._cache)} (max: 5)")
        print(f"   LRU eviction working as expected")

        return True

    except Exception as e:
        print(f"❌ Query cache test failed: {e}")
        return False


def test_example_data_exists():
    """Test that example data file exists and is valid JSON."""
    print("\n" + "="*60)
    print("TEST 6: Example Data")
    print("="*60)

    try:
        data_path = Path(__file__).parent / "example_data.json"

        assert data_path.exists(), f"example_data.json should exist at {data_path}"

        with open(data_path) as f:
            data = json.load(f)

        assert "sample_queries" in data, "Data should have 'sample_queries'"
        assert "sample_documents" in data, "Data should have 'sample_documents'"
        assert "cost_estimates" in data, "Data should have 'cost_estimates'"

        print("✅ Example data loaded successfully")
        print(f"   Sample queries: {len(data['sample_queries'])}")
        print(f"   Sample documents: {len(data['sample_documents'])}")

        return True

    except Exception as e:
        print(f"❌ Example data test failed: {e}")
        return False


def test_fastapi_app_creates():
    """Test that FastAPI app can be created."""
    print("\n" + "="*60)
    print("TEST 7: FastAPI App Creation")
    print("="*60)

    try:
        from app import create_app

        app = create_app()

        assert app is not None, "App should not be None"
        assert hasattr(app, 'routes'), "App should have routes"

        # Check that expected routes exist
        route_paths = [route.path for route in app.routes]

        assert "/health" in route_paths, "App should have /health endpoint"
        assert "/query" in route_paths, "App should have /query endpoint"
        assert "/memory" in route_paths, "App should have /memory endpoint"

        print("✅ FastAPI app created successfully")
        print(f"   Total routes: {len(route_paths)}")
        print(f"   Routes: {', '.join(sorted(route_paths)[:5])}")

        return True

    except Exception as e:
        print(f"❌ FastAPI app test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all smoke tests and report results."""
    print("\n" + "="*70)
    print(" "*15 + "MODULE 7.2 - SMOKE TESTS")
    print("="*70)

    tests = [
        test_config_loads,
        test_apm_manager_initializes,
        test_pipeline_processes_query,
        test_memory_profiler,
        test_query_cache,
        test_example_data_exists,
        test_fastapi_app_creates,
    ]

    results = []
    for test in tests:
        try:
            success = test()
            results.append((test.__name__, success))
        except Exception as e:
            print(f"\n❌ Test {test.__name__} crashed: {e}")
            results.append((test.__name__, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("\n" + "="*70)
    print(f"Results: {passed}/{total} tests passed")
    print("="*70 + "\n")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
