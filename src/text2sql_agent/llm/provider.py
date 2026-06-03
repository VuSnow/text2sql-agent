"""LLM provider factory.

Creates LangChain chat model instances based on configuration.
Supports OpenAI and AWS Bedrock (Claude).
"""

import boto3
from langchain_aws import ChatBedrockConverse
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
        kwargs: dict = {
            "model": model,
            "temperature": temperature,
        }
        if settings.llm_api_key:
            kwargs["api_key"] = settings.llm_api_key
        return ChatOpenAI(**kwargs)

    if provider == LLMProvider.BEDROCK:
        session = boto3.Session(
            region_name=settings.aws_region,
            profile_name=settings.aws_profile,
        )
        return ChatBedrockConverse(
            model=model,
            temperature=temperature,
            client=session.client("bedrock-runtime"),
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
