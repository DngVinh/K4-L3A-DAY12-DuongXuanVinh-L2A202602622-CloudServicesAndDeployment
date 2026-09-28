"""DeepSeek chat provider.

The API key stays on the server. The public browser only sends the service's
``X-API-Key``; it never receives ``DEEPSEEK_API_KEY``.
"""

from __future__ import annotations

from collections.abc import Iterable

import httpx

from .config import Settings


class DeepSeekProviderError(RuntimeError):
    """A safe, user-facing provider error that never contains the API key."""


def _estimate_tokens(text: str) -> int:
    """Fallback estimate for providers that omit usage."""
    return max(1, len(text) // 4)


def _message_content(value: object) -> str:
    """Normalize the text content shape returned by chat-completions."""
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        chunks: list[str] = []
        for part in value:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks)
    return ""


def _usage_cost(
    usage: dict,
    settings: Settings,
    *,
    fallback_input: int,
    fallback_output: int,
) -> tuple[int, int, float]:
    prompt_tokens = int(usage.get("prompt_tokens") or fallback_input)
    completion_tokens = int(usage.get("completion_tokens") or fallback_output)

    details = usage.get("prompt_tokens_details")
    cached_tokens = usage.get("prompt_cache_hit_tokens")
    if cached_tokens is None and isinstance(details, dict):
        cached_tokens = details.get("cached_tokens")
    cached_tokens = min(max(int(cached_tokens or 0), 0), prompt_tokens)
    uncached_tokens = prompt_tokens - cached_tokens

    cost = (
        uncached_tokens * settings.deepseek_input_price_per_million
        + cached_tokens * settings.deepseek_input_cache_price_per_million
        + completion_tokens * settings.deepseek_output_price_per_million
    ) / 1_000_000
    return prompt_tokens, completion_tokens, round(cost, 8)


def ask_deepseek(question: str, history: list[dict], settings: Settings) -> dict:
    """Call DeepSeek Chat Completions and adapt it to the app response contract."""
    api_key = settings.deepseek_api_key
    if not api_key:
        raise DeepSeekProviderError(
            "DeepSeek is enabled but DEEPSEEK_API_KEY is not configured"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are CloudPilot, a concise and practical cloud and DevOps "
                "assistant. Answer in the user's language, give actionable steps, "
                "and never claim to have run a command you did not run."
            ),
        }
    ]
    messages.extend(
        {
            "role": turn["role"],
            "content": str(turn.get("content", "")),
        }
        for turn in history
        if turn.get("role") in {"user", "assistant"}
    )
    messages.append({"role": "user", "content": question})

    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "max_tokens": settings.deepseek_max_tokens,
        "stream": False,
    }

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.deepseek_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
    except httpx.TimeoutException as exc:
        raise DeepSeekProviderError("DeepSeek request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise DeepSeekProviderError(
            f"DeepSeek returned HTTP {exc.response.status_code}"
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise DeepSeekProviderError("DeepSeek request could not be completed") from exc

    try:
        choice = body["choices"][0]
        message = choice["message"]
        answer = _message_content(message.get("content"))
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekProviderError("DeepSeek returned an unexpected response") from exc

    if not answer.strip():
        raise DeepSeekProviderError("DeepSeek returned an empty answer")

    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    fallback_input = _estimate_tokens(
        question + "".join(str(t.get("content", "")) for t in history)
    )
    fallback_output = _estimate_tokens(answer)
    tokens_in, tokens_out, cost_usd = _usage_cost(
        usage,
        settings,
        fallback_input=fallback_input,
        fallback_output=fallback_output,
    )
    return {
        "answer": answer,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
    }
