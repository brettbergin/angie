"""Tests for angie.llm."""

from unittest.mock import MagicMock, patch


def _mock_settings(
    github_token=None,
    openai_api_key=None,
    anthropic_api_key=None,
    llm_provider="github",
    anthropic_model="claude-sonnet-4-20250514",
):
    s = MagicMock()
    s.github_token = github_token
    s.openai_api_key = openai_api_key
    s.anthropic_api_key = anthropic_api_key
    s.llm_provider = llm_provider
    s.copilot_model = "gpt-4o"
    s.anthropic_model = anthropic_model
    s.github_models_api_base = "https://models.github.ai/inference"
    return s


def test_get_llm_model_cached():
    """get_llm_model returns cached model on second call."""
    import angie.llm as llm_mod

    mock_model = MagicMock()
    llm_mod._model_cache = None
    llm_mod._model_expires_at = 0.0

    with patch.object(llm_mod, "_build_model", return_value=(mock_model, float("inf"))) as build:
        m1 = llm_mod.get_llm_model()
        m2 = llm_mod.get_llm_model()
        assert m1 is mock_model
        assert m2 is mock_model
        build.assert_called_once()

    # Reset
    llm_mod._model_cache = None
    llm_mod._model_expires_at = 0.0


def test_get_llm_model_force_refresh():
    import angie.llm as llm_mod

    mock_model = MagicMock()
    llm_mod._model_cache = MagicMock()
    llm_mod._model_expires_at = float("inf")

    with patch.object(llm_mod, "_build_model", return_value=(mock_model, float("inf"))) as build:
        m = llm_mod.get_llm_model(force_refresh=True)
        assert m is mock_model
        build.assert_called_once()

    llm_mod._model_cache = None
    llm_mod._model_expires_at = 0.0


def test_get_llm_model_expired():
    """Model is rebuilt when expires_at is in the past."""
    import angie.llm as llm_mod

    mock_model = MagicMock()
    llm_mod._model_cache = MagicMock()
    llm_mod._model_expires_at = 0.0  # expired

    with patch.object(llm_mod, "_build_model", return_value=(mock_model, float("inf"))) as build:
        m = llm_mod.get_llm_model()
        assert m is mock_model
        build.assert_called_once()

    llm_mod._model_cache = None
    llm_mod._model_expires_at = 0.0


def test_build_model_with_github_token():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(github_token="gh-tok", llm_provider="github")
    mock_model = MagicMock()
    mock_provider = MagicMock()
    mock_openai_model_cls = MagicMock(return_value=mock_model)
    mock_provider_cls = MagicMock(return_value=mock_provider)

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("pydantic_ai.models.openai.OpenAIModel", mock_openai_model_cls),
        patch("pydantic_ai.providers.openai.OpenAIProvider", mock_provider_cls),
    ):
        model, expires_at = llm_mod._build_model()
        import math

        assert math.isinf(expires_at)
        mock_provider_cls.assert_called_once_with(
            base_url="https://models.github.ai/inference",
            api_key="gh-tok",
        )


def test_build_model_with_openai_key():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(openai_api_key="sk-test", llm_provider="openai")
    mock_model = MagicMock()
    mock_provider = MagicMock()
    mock_openai_model_cls = MagicMock(return_value=mock_model)
    mock_provider_cls = MagicMock(return_value=mock_provider)

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("pydantic_ai.models.openai.OpenAIModel", mock_openai_model_cls),
        patch("pydantic_ai.providers.openai.OpenAIProvider", mock_provider_cls),
    ):
        model, expires_at = llm_mod._build_model()
        import math

        assert math.isinf(expires_at)


def test_build_model_no_config_raises():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(llm_provider="github")

    with patch("angie.config.get_settings", return_value=mock_settings):
        try:
            llm_mod._build_model()
            raise AssertionError("Should have raised RuntimeError")
        except RuntimeError as e:
            assert "GITHUB_TOKEN" in str(e)


def test_is_llm_configured_true():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(github_token="gh-tok")
    with patch("angie.config.get_settings", return_value=mock_settings):
        assert llm_mod.is_llm_configured() is True


def test_is_llm_configured_false():
    import angie.llm as llm_mod

    mock_settings = _mock_settings()
    with patch("angie.config.get_settings", return_value=mock_settings):
        assert llm_mod.is_llm_configured() is False


def test_is_llm_configured_openai():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(openai_api_key="sk-test", llm_provider="openai")
    with patch("angie.config.get_settings", return_value=mock_settings):
        assert llm_mod.is_llm_configured() is True


def test_build_model_with_anthropic_key():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(anthropic_api_key="sk-ant-test", llm_provider="anthropic")
    mock_model = MagicMock()
    mock_provider = MagicMock()
    mock_anthropic_model_cls = MagicMock(return_value=mock_model)
    mock_provider_cls = MagicMock(return_value=mock_provider)

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("pydantic_ai.models.anthropic.AnthropicModel", mock_anthropic_model_cls),
        patch("pydantic_ai.providers.anthropic.AnthropicProvider", mock_provider_cls),
    ):
        model, expires_at = llm_mod._build_model()
        import math

        assert math.isinf(expires_at)
        mock_provider_cls.assert_called_once_with(api_key="sk-ant-test")
        mock_anthropic_model_cls.assert_called_once_with(
            "claude-sonnet-4-20250514", provider=mock_provider
        )


def test_build_model_anthropic_missing_key():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(llm_provider="anthropic")

    with patch("angie.config.get_settings", return_value=mock_settings):
        try:
            llm_mod._build_model()
            raise AssertionError("Should have raised RuntimeError")
        except RuntimeError as e:
            assert "ANTHROPIC_API_KEY" in str(e)


def test_build_model_openai_missing_key():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(llm_provider="openai")

    with patch("angie.config.get_settings", return_value=mock_settings):
        try:
            llm_mod._build_model()
            raise AssertionError("Should have raised RuntimeError")
        except RuntimeError as e:
            assert "OPENAI_API_KEY" in str(e)


def test_is_llm_configured_anthropic():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(anthropic_api_key="sk-ant-test", llm_provider="anthropic")
    with patch("angie.config.get_settings", return_value=mock_settings):
        assert llm_mod.is_llm_configured() is True


def test_is_llm_configured_anthropic_no_key():
    import angie.llm as llm_mod

    mock_settings = _mock_settings(llm_provider="anthropic")
    with patch("angie.config.get_settings", return_value=mock_settings):
        assert llm_mod.is_llm_configured() is False
