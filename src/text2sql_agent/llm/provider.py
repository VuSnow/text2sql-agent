"""LLM provider factory.

Creates LangChain chat model instances based on configuration.
Currently supports OpenAI; extensible to other providers.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from text2sql_agent.config import LLMProvider, settings


def get_llm(
    provider: LLMProvider | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """Create a chat model instance from config (or overrides).

    Args:
        provider: LLM provider. Defaults to settings.llm_provider.
        model: Model name. Defaults to settings.llm_model.
        temperature: Sampling temperature. Defaults to settings.llm_temperature.

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ValueError: If the provider is not supported.
    """
    provider = provider or settings.llm_provider
    model = model or settings.llm_model
    temperature = temperature if temperature is not None else settings.llm_temperature

    if provider == LLMProvider.OPENAI:
        return ChatOpenAI(
            model=model,
            api_key=settings.llm_api_key,
            temperature=temperature,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
