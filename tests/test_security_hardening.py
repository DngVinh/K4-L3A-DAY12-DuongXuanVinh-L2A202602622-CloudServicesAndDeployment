"""Regression tests for the security contract beyond the original lab rubric."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.cost_guard import CostGuard
from app.rate_limiter import RateLimiter


def test_client_header_cannot_select_another_history(client_real_store, api_key, monkeypatch):
    monkeypatch.setenv("STRICT_API_IDENTITY", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": api_key}
    try:
        first = client_real_store.post(
            "/ask", json={"question": "private message"},
            headers={**headers, "X-User-Id": "alice"},
        )
        second = client_real_store.post(
            "/ask", json={"question": "next"},
            headers={**headers, "X-User-Id": "bob"},
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["user_id"] == second.json()["user_id"] == "owner"
        assert second.json()["history_length"] == 2
    finally:
        get_settings.cache_clear()


def test_legacy_client_selected_history_is_not_attached(client_real_store, fake_redis, api_key, monkeypatch):
    monkeypatch.setenv("STRICT_API_IDENTITY", "true")
    get_settings.cache_clear()
    try:
        fake_redis.rpush("history:owner", json.dumps({"role": "user", "content": "untrusted legacy data"}))
        response = client_real_store.post(
            "/ask", json={"question": "new session"}, headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json()["history_length"] == 0
    finally:
        get_settings.cache_clear()


def test_dedicated_keys_have_separate_identity(client_real_store, monkeypatch):
    monkeypatch.setenv("STRICT_API_IDENTITY", "true")
    monkeypatch.setenv("AGENT_API_KEYS", '{"alice":"alice-test-key-0123456789-abcdefghi","bob":"bob-test-key-0123456789-abcdefghijk"}')
    get_settings.cache_clear()
    try:
        alice = client_real_store.post(
            "/ask", json={"question": "alice secret"},
            headers={"X-API-Key": "alice-test-key-0123456789-abcdefghi", "X-User-Id": "bob"},
        )
        bob = client_real_store.post(
            "/ask", json={"question": "bob question"},
            headers={"X-API-Key": "bob-test-key-0123456789-abcdefghijk", "X-User-Id": "alice"},
        )
        assert alice.status_code == bob.status_code == 200
        assert alice.json()["user_id"] == "alice"
        assert bob.json()["user_id"] == "bob"
        assert bob.json()["history_length"] == 0
    finally:
        get_settings.cache_clear()


def test_rate_limit_is_atomic(fake_redis):
    limiter = RateLimiter(fake_redis, limit_per_minute=3)

    def call():
        try:
            limiter.check("same-client", now=1000.0)
            return True
        except HTTPException as exc:
            assert exc.status_code in (429, 503)
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: call(), range(8)))
    assert results.count(True) == 3


def test_global_budget_reservation_is_atomic(fake_redis):
    guard = CostGuard(fake_redis, monthly_budget_usd=0.001, global_budget_usd=0.001)

    def call():
        try:
            guard.reserve("same-client", 0.0006)
            return True
        except HTTPException as exc:
            assert exc.status_code in (402, 503)
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: call(), range(8)))
    assert results.count(True) == 1
    assert guard.spent("same-client") == pytest.approx(0.0006)


def test_strict_mode_blocks_before_provider(client_factory, api_key, monkeypatch):
    monkeypatch.setenv("STRICT_API_IDENTITY", "true")
    get_settings.cache_clear()
    called = False

    def provider(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be called")

    monkeypatch.setattr("app.main.ask_llm", provider)
    try:
        client = client_factory(budget=0.00001)
        response = client.post(
            "/ask", json={"question": "expensive"},
            headers={"X-API-Key": api_key, "X-User-Id": "arbitrary"},
        )
        assert response.status_code == 402
        assert called is False
    finally:
        get_settings.cache_clear()


def test_browser_key_is_not_persisted_and_redis_not_published(repo_root):
    frontend = (repo_root / "frontend" / "app.js").read_text(encoding="utf-8")
    compose = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "sessionStorage" not in frontend
    assert "localStorage" not in frontend
    assert '"X-User-Id"' not in frontend
    assert '"127.0.0.1:6379:6379"' in compose
