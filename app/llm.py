"""Provider switch for the agent's language model."""

from __future__ import annotations

from .config import get_settings
from .deepseek import DeepSeekProviderError, ask_deepseek
from utils.mock_llm import ask_llm as ask_mock_llm


def ask_llm(question: str, history: list[dict] | None = None) -> dict:
    """Use the configured provider while keeping the existing response contract."""
    settings = get_settings()
    history = history or []
    if settings.llm_provider.strip().lower() == "deepseek":
        return ask_deepseek(question, history, settings)
    return ask_mock_llm(question, history)


__all__ = ["DeepSeekProviderError", "ask_llm"]
