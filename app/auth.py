"""CP3 — Xác thực bằng API key.

Public URL = ai cũng gọi được. Không có lớp này, hóa đơn LLM của bạn do
người lạ quyết định.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from .config import get_settings

ANONYMOUS_USER = "anonymous"


def verify_api_key(
    x_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    """Keep the lab contract; optionally bind identities to keys in secure mode."""
    settings = get_settings()
    if x_api_key is not None and secrets.compare_digest(x_api_key, settings.agent_api_key):
        return "owner" if settings.strict_api_identity else (x_user_id or ANONYMOUS_USER)
    for user_id, key in settings.agent_api_keys.items():
        if x_api_key is not None and secrets.compare_digest(x_api_key, key):
            return user_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or missing API key",
    )
