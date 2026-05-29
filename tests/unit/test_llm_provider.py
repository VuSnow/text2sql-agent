"""Unit tests for LLM provider factory."""

from unittest.mock import patch

import pytest
from langchain_openai import ChatOpenAI

from text2sql_agent.config import LLMProvider
from text2sql_agent.llm.provider import get_llm


def test_get_llm_returns_openai_instance():
    """Default provider returns ChatOpenAI with correct config."""
    with patch("text2sql_agent.llm.provider.settings") as mock_settings:
        mock_settings.llm_provider = LLMProvider.OPENAI
        mock_settings.llm_model = "gpt-4o"
        mock_settings.llm_api_key = "sk-test-key"
        mock_settings.llm_temperature = 0.0

        llm = get_llm()

    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o"
    assert llm.temperature == 0.0


def test_get_llm_respects_overrides():
    """Explicit parameters override settings."""
    with patch("text2sql_agent.llm.provider.settings") as mock_settings:
        mock_settings.llm_provider = LLMProvider.OPENAI
        mock_settings.llm_model = "gpt-4o"
        mock_settings.llm_api_key = "sk-test-key"
        mock_settings.llm_temperature = 0.0

        llm = get_llm(model="gpt-4o-mini", temperature=0.7)

    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o-mini"
    assert llm.temperature == 0.7


def test_get_llm_unsupported_provider_raises():
    """Unknown provider raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm(provider="anthropic")
