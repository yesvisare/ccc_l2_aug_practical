# Migration Guide: TVH Baseline Structure

## Quick Reference

### Running the Application

**Before:**
```bash
python app.py
```

**After (same, but cleaner):**
```bash
python app.py
# OR use Windows script:
.\scripts\run_api.ps1
```

### Running Tests

**Before:**
```bash
pytest tests_smoke.py
```

**After:**
```bash
pytest
# OR use Windows script:
.\scripts\run_tests.ps1
```

### Import Changes

**Before:**
```python
import l2_m7_custom_business_metrics as metrics
from config import load_config
```

**After:**
```python
from src.m7_custom_business_metrics import core as metrics
from src.m7_custom_business_metrics.config import load_config

# OR use package-level imports:
from src.m7_custom_business_metrics import (
    UserCohort, QueryAccuracy, get_user_cohort, load_config
)
```

### API Endpoint Changes

**Before:**
- `GET /health`
- `POST /metrics/query`
- `GET /metrics`

**After:**
- `GET /health` (unchanged, app-level)
- `POST /api/metrics/query` (now under /api prefix)
- `GET /api/metrics` (now under /api prefix)

### File Locations

| File Type | Before | After |
|-----------|--------|-------|
| Core logic | `l2_m7_custom_business_metrics.py` | `src/m7_custom_business_metrics/core.py` |
| Config | `config.py` | `src/m7_custom_business_metrics/config.py` |
| API routes | `app.py` (mixed) | `src/m7_custom_business_metrics/api.py` |
| Tests | `tests_smoke.py` | `tests/test_smoke.py` |
| Notebook | `L2_M7_Custom_Business_Metrics.ipynb` | `notebooks/L2_M7_Custom_Business_Metrics.ipynb` |
| Data | `example_data.json` | `data/example_data.json` |

## What Changed?

### 1. Thin app.py
- Reduced from 387 lines to 81 lines
- Only contains FastAPI app setup and /health endpoint
- All business logic extracted to package

### 2. Package Structure
- All code under `src/m7_custom_business_metrics/`
- Proper `__init__.py` with exports
- API routes in separate `api.py`

### 3. Tests
- Moved to `tests/` directory
- Pytest auto-discovery works
- Import paths updated

### 4. Windows Scripts
- `scripts/run_api.ps1` - Run development server
- `scripts/run_tests.ps1` - Run pytest
- `scripts/print_tree.ps1` - Show directory structure

### 5. Organization
- `data/` - Example and test data
- `notebooks/` - Jupyter notebooks
- `scripts/` - Helper scripts

## Breaking Changes

❌ **Old imports won't work:**
```python
import l2_m7_custom_business_metrics  # BROKEN
from config import load_config         # BROKEN
```

✅ **Use new imports:**
```python
from src.m7_custom_business_metrics import core
from src.m7_custom_business_metrics.config import load_config
```

❌ **Old API paths (if you have hardcoded clients):**
```
POST /metrics/query  # BROKEN
```

✅ **New API paths:**
```
POST /api/metrics/query  # WORKS
```

## No Behavior Changes

✓ All business logic identical (zero changes)
✓ All API endpoints work the same (just different URLs)
✓ All tests pass with same assertions
✓ Configuration loading unchanged
✓ Prometheus metrics identical

## Benefits

1. **Clear separation**: Business logic in package, app.py is thin
2. **Pytest discovery**: Tests auto-discovered in `tests/`
3. **Better imports**: Proper Python package structure
4. **Organized files**: Notebooks, data, scripts in dedicated folders
5. **Windows support**: PowerShell scripts for common tasks
6. **Git hygiene**: .gitignore for common artifacts
7. **Scalable**: Easy to add more modules under `src/`
