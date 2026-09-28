"""CP3 — Cost guard: chặn chi phí trước khi hóa đơn chặn bạn.

Rate limit giới hạn *số lượng* request. Cost guard giới hạn *số tiền*: một
user gửi 10 request/phút nhưng mỗi request 50k token vẫn đốt sạch ngân sách.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from redis.exceptions import WatchError

# Giữ dữ liệu chi tiêu thêm ~40 ngày để còn đối soát sang tháng sau
KEY_TTL_SECONDS = 40 * 24 * 3600


def estimate_max_cost(question: str, history: list[dict], settings) -> float:
    """Conservative text-only cost bound for one DeepSeek request."""
    input_bytes = len(question.encode("utf-8")) + sum(
        len(str(turn.get("content", "")).encode("utf-8")) for turn in history
    )
    input_tokens = input_bytes + 64 * (len(history) + 2)
    estimated = (
        Decimal(input_tokens) * Decimal(str(settings.deepseek_input_price_per_million))
        + Decimal(settings.deepseek_max_tokens) * Decimal(str(settings.deepseek_output_price_per_million))
    ) / Decimal(1_000_000)
    return float(max(estimated, Decimal("0.00000001")))


class CostGuard:
    def __init__(self, client, monthly_budget_usd: float, global_budget_usd: float | None = None) -> None:
        self.client = client
        self.budget = monthly_budget_usd
        self.global_budget = global_budget_usd

    @staticmethod
    def current_month() -> str:
        """CHO SẴN — nhãn tháng hiện tại dạng '2026-08' (UTC)."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @classmethod
    def _key(cls, user_id: str, month: str | None = None) -> str:
        """CHO SẴN — khóa Redis theo từng user, từng tháng."""
        return f"cost:{user_id}:{month or cls.current_month()}"

    @classmethod
    def _global_key(cls, month: str | None = None) -> str:
        return f"service_cost:{month or cls.current_month()}"

    def spent(self, user_id: str, month: str | None = None) -> float:
        """Số tiền user đã tiêu trong tháng.

        TODO (CP3): đọc ``self.client.get(self._key(user_id, month))``.
        Key chưa tồn tại → Redis trả None → hàm này phải trả ``0.0``.
        Nhớ ép kiểu ``float(...)`` vì Redis trả về chuỗi.
        """
        value = self.client.get(self._key(user_id, month))
        return 0.0 if value is None else float(value)

    def check(
        self,
        user_id: str,
        estimated_cost: float = 0.0,
        month: str | None = None,
    ) -> None:
        """Cho qua nếu còn ngân sách, ngược lại raise 402.

        TODO (CP3): nếu ``spent(user_id) + estimated_cost > self.budget``
        → raise ``HTTPException(status_code=402, detail="monthly budget exceeded")``.
        402 = Payment Required, đúng ngữ nghĩa cho tình huống hết ngân sách.
        """
        if self.spent(user_id, month) + estimated_cost > self.budget:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="monthly budget exceeded",
            )

    def record(self, user_id: str, cost: float, month: str | None = None) -> float:
        """Cộng dồn chi phí vừa phát sinh, trả về tổng mới.

        TODO (CP3):
          1. ``total = self.client.incrbyfloat(key, cost)``
          2. ``self.client.expire(key, KEY_TTL_SECONDS)``
          3. ``return float(total)``
        """
        key = self._key(user_id, month)
        with self.client.pipeline(transaction=True) as pipe:
            pipe.incrbyfloat(key, cost)
            pipe.expire(key, KEY_TTL_SECONDS)
            if self.global_budget is not None:
                global_key = self._global_key(month)
                pipe.incrbyfloat(global_key, cost)
                pipe.expire(global_key, KEY_TTL_SECONDS)
            result = pipe.execute()
        return float(result[0])

    def reserve(self, user_id: str, estimated_cost: float) -> tuple[str, str | None, float]:
        """Reserve spend for this user and the service in one transaction."""
        if estimated_cost <= 0:
            raise ValueError("estimated cost must be positive")
        user_key = self._key(user_id)
        global_key = self._global_key() if self.global_budget is not None else None
        keys = [user_key] + ([global_key] if global_key else [])
        estimate = Decimal(str(estimated_cost))
        for _ in range(20):
            try:
                with self.client.pipeline() as pipe:
                    pipe.watch(*keys)
                    user_spent = Decimal(str(pipe.get(user_key) or 0))
                    global_spent = Decimal(str(pipe.get(global_key) or 0)) if global_key else Decimal(0)
                    if user_spent + estimate > Decimal(str(self.budget)) or (
                        global_key and global_spent + estimate > Decimal(str(self.global_budget))
                    ):
                        raise HTTPException(status_code=402, detail="monthly budget exceeded")
                    pipe.multi()
                    for key in keys:
                        pipe.incrbyfloat(key, str(estimate))
                        pipe.expire(key, KEY_TTL_SECONDS)
                    pipe.execute()
                    return user_key, global_key, float(estimate)
            except WatchError:
                continue
        raise HTTPException(status_code=503, detail="budget guard busy")

    def settle(self, reservation: tuple[str, str | None, float], actual_cost: float) -> None:
        """Adjust the reservation after a successful provider response."""
        user_key, global_key, estimated = reservation
        delta = Decimal(str(actual_cost)) - Decimal(str(estimated))
        if delta:
            with self.client.pipeline(transaction=True) as pipe:
                pipe.incrbyfloat(user_key, str(delta))
                if global_key:
                    pipe.incrbyfloat(global_key, str(delta))
                pipe.execute()
