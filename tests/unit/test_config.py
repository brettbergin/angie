"""Tests for angie.config."""

import os
from unittest.mock import patch


def make_settings(**kwargs):
    """Helper to create Settings with required fields."""
    from angie.config import Settings

    defaults = {"secret_key": "test-secret", "db_password": "test-pass"}
    defaults.update(kwargs)
    return Settings(**defaults)  # type: ignore[call-arg]


def test_settings_defaults():
    # Unset env vars that CI may inject (e.g. from the MySQL service container)
    # so we test the Settings field defaults, not ambient env values.
    ci_vars = {"DB_NAME", "DB_USER", "DB_HOST", "DB_PORT", "APP_ENV", "DEBUG"}
    clean_env = {k: v for k, v in os.environ.items() if k not in ci_vars}
    with patch.dict(os.environ, clean_env, clear=True):
        s = make_settings()
    assert s.app_name == "Angie"
    assert s.app_env == "development"
    assert s.debug is False
    assert s.db_host == "localhost"
    assert s.db_port == 3306
    assert s.db_name == "angie"
    assert s.db_user == "angie"


def test_database_url():
    s = make_settings(db_user="u", db_password="p", db_host="h", db_port=3306, db_name="db")
    assert s.database_url == "mysql+aiomysql://u:p@h:3306/db"


def test_database_url_sync():
    s = make_settings(db_user="u", db_password="p", db_host="h", db_port=3306, db_name="db")
    assert s.database_url_sync == "mysql+pymysql://u:p@h:3306/db"


def test_redis_url_no_password():
    s = make_settings(redis_host="localhost", redis_port=6379, redis_db=0)
    assert s.redis_url == "redis://localhost:6379/0"


def test_redis_url_with_password():
    s = make_settings(redis_password="mypass", redis_host="rhost", redis_port=6380, redis_db=1)
    assert s.redis_url == "redis://:mypass@rhost:6380/1"


def test_effective_celery_broker_default():
    s = make_settings()
    assert s.effective_celery_broker == s.redis_url


def test_effective_celery_broker_custom():
    s = make_settings(celery_broker_url="redis://custom:6379/2")
    assert s.effective_celery_broker == "redis://custom:6379/2"


def test_effective_celery_backend_default():
    s = make_settings()
    assert s.effective_celery_backend == s.redis_url


def test_effective_celery_backend_custom():
    s = make_settings(celery_result_backend="redis://custom:6379/3")
    assert s.effective_celery_backend == "redis://custom:6379/3"


def test_jwt_defaults():
    s = make_settings()
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_access_token_expire_minutes == 30
    assert s.jwt_refresh_token_expire_days == 30


def test_copilot_defaults():
    s = make_settings()
    assert s.copilot_model == "gpt-4o"
    assert s.copilot_api_base == "https://api.githubcopilot.com"
    # github_token and openai_api_key may be set by .env; just verify types
    assert s.github_token is None or isinstance(s.github_token, str)
    assert s.openai_api_key is None or isinstance(s.openai_api_key, str)


def test_get_settings_cached():
    from angie.config import get_settings

    with patch.dict(os.environ, {"SECRET_KEY": "s", "DB_PASSWORD": "p"}):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()
