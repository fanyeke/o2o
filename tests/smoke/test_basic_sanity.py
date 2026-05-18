"""Smoke tests - basic sanity checks for critical paths.

These tests verify that the most fundamental operations work correctly.
If any of these fail, the system is not functional.

Test categories:
1. Environment setup (Python version, dependencies)
2. Database connectivity (PostgreSQL, migrations)
3. Configuration loading (env vars, settings)
4. Data pipeline basics (import, clean, features)
5. API startup (FastAPI app, health endpoint)
"""

import sys
import subprocess
from pathlib import Path


def test_python_version():
    """Verify Python version is 3.12+."""
    version = sys.version_info
    assert version.major == 3 and version.minor >= 12, \
        f"Python 3.12+ required, got {version.major}.{version.minor}"


def test_dependencies_installed():
    """Verify critical dependencies are installed."""
    critical_deps = [
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "celery",
        "lightgbm",
        "pandas",
    ]

    for dep in critical_deps:
        try:
            __import__(dep)
        except ImportError:
            raise AssertionError(f"Critical dependency '{dep}' not installed")


def test_project_structure():
    """Verify critical project files exist."""
    critical_files = [
        "app/main.py",
        "app/core/config.py",
        "app/core/database.py",
        ".env.example",
        "requirements.txt",
        "alembic.ini",
        "scripts/init_metrics.py",
    ]

    for file_path in critical_files:
        path = Path(file_path)
        assert path.exists(), f"Critical file missing: {file_path}"


def test_env_file_exists():
    """Verify .env file exists (or can be created from .env.example)."""
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    assert env_path.exists() or env_example_path.exists(), \
        "No .env or .env.example file found"


def test_config_loading():
    """Verify Settings can be loaded."""
    from app.core.config import get_settings

    settings = get_settings()
    assert settings is not None
    assert hasattr(settings, "database_url")
    assert hasattr(settings, "api_token")


def test_database_url_format():
    """Verify DATABASE_URL format is correct."""
    from app.core.config import get_settings

    settings = get_settings()
    db_url = settings.database_url

    # Should contain postgresql
    assert "postgresql" in db_url, \
        f"DATABASE_URL should contain postgresql, got: {db_url}"


def test_init_metrics_script_imports():
    """Verify init_metrics.py can import required modules."""
    # This catches import errors before running the actual script
    try:
        from app.features.merchant_features import MerchantFeatureCalculator
        from app.features.user_features import calculate_user_metrics
        from app.features.coupon_features import CouponFeatureCalculator
        from app.services.data_cleaning_service import DataCleaningService
    except ImportError as e:
        raise AssertionError(f"init_metrics.py imports failed: {e}")


def test_init_metrics_subprocess_call():
    """Verify init_metrics.py uses sys.executable, not 'python'."""
    script_path = Path("scripts/init_metrics.py")
    content = script_path.read_text()

    # Check subprocess calls use sys.executable
    assert "sys.executable" in content, \
        "init_metrics.py should use sys.executable for subprocess calls"

    # Should NOT have hardcoded "python"
    lines_with_python = [
        line for line in content.split('\n')
        if 'cmd = ["python"' in line
    ]

    assert len(lines_with_python) == 0, \
        f"Found hardcoded 'python' in subprocess calls: {lines_with_python}"


def test_agent_tools_registry():
    """Verify Agent tools are properly registered."""
    from app.agents.tools import AVAILABLE_TOOLS

    required_tools = [
        "get_merchant_metrics",
        "get_coupon_conversion",
        "get_user_metrics",
        "get_recent_receipts",
    ]

    for tool_name in required_tools:
        assert tool_name in AVAILABLE_TOOLS, \
            f"Required tool '{tool_name}' not registered"


def test_agent_prompt_formatting():
    """Verify Agent prompt formatting doesn't crash with tool outputs."""
    # Import at module level to check structure exists
    import sys
    sys.path.insert(0, '/home/zzz/project/o2o')
    from app.agents.prompts import decision_prompt

    # Mock tool output matching actual structure
    mock_tool_results = {
        "merchant_metrics": {
            "merchant_id": "test_merchant",
            "metrics": {
                "total_receipts_7d": 100,
                "redeemed_rate_7d": 0.5,
                "total_receipts_30d": 300,
                "redeemed_rate_30d": 0.4,
                "redeemed_rate_change": 0.25,
                "avg_discount_depth": 0.15,
                "activity_health_score": 7.5,
            },
            "evidence": [
                {"type": "test", "content": "test evidence"}
            ]
        },
        "coupon_conversion": {
            "merchant_id": "test_merchant",
            "total_coupons": 5,
            "coupons": [
                {
                    "coupon_id": "coupon_001",
                    "conversion_metrics": {
                        "discount_type": "满减",
                        "redeemed_rate": 0.50,
                        "avg_redeem_days": 5.0,
                    },
                    "evidence": []
                }
            ]
        }
    }

    # Test _format_tool_results function directly (it's a module-level function)
    formatted = decision_prompt._format_tool_results(mock_tool_results)

    # Should not raise KeyError or any exception
    assert formatted is not None
    assert len(formatted) > 0
    assert "商户指标" in formatted or "优惠券转化数据" in formatted


def test_fastapi_app_startup():
    """Verify FastAPI app can be instantiated."""
    from app.main import app

    assert app is not None
    assert app.title


def test_health_router_registered():
    """Verify health check endpoint is registered."""
    from app.main import app

    # Find health router
    health_routes = [
        route for route in app.routes
        if hasattr(route, 'path') and '/health' in route.path
    ]

    assert len(health_routes) > 0, "Health endpoint not registered"


if __name__ == "__main__":
    # Run all tests
    print("Running smoke tests...\n")

    tests = [
        test_python_version,
        test_dependencies_installed,
        test_project_structure,
        test_env_file_exists,
        test_config_loading,
        test_database_url_format,
        test_init_metrics_script_imports,
        test_init_metrics_subprocess_call,
        test_agent_tools_registry,
        test_agent_prompt_formatting,
        test_fastapi_app_startup,
        test_health_router_registered,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: Unexpected error: {e}")
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")

    if failed > 0:
        print("\n⚠️  CRITICAL: Smoke tests failed. System is not functional.")
        sys.exit(1)
    else:
        print("\n✓ All smoke tests passed. System is ready.")
        sys.exit(0)