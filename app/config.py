"""CP1 — Cấu hình theo 12-Factor.

Nguyên tắc: **không có giá trị cấu hình nào nằm trong code**. Tất cả đến từ
biến môi trường, để cùng một image chạy được ở laptop, staging và production
mà không phải sửa một dòng code nào.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toàn bộ cấu hình của service.

    TODO (CP1): khai báo các trường dưới đây. pydantic-settings tự đọc biến
    môi trường theo tên trường (không phân biệt hoa thường), nên trường
    ``agent_api_key`` sẽ lấy giá trị từ biến ``AGENT_API_KEY``.

    | Trường                  | Kiểu  | Mặc định                   |
    |-------------------------|-------|----------------------------|
    | port                    | int   | 8000                       |
    | agent_api_key           | str   | KHÔNG có mặc định (bắt buộc)|
    | redis_url               | str   | "redis://localhost:6379/0" |
    | rate_limit_per_minute   | int   | 10                         |
    | monthly_budget_usd      | float | 10.0                       |
    | log_level               | str   | "INFO"                     |
    | llm_provider            | str   | "mock"                     |
    | deepseek_api_key        | str   | không mặc định              |
    | deepseek_model          | str   | "deepseek-flash"            |

    Vì sao ``agent_api_key`` không được có giá trị mặc định? Vì mặc định
    nghĩa là app vẫn khởi động khi bạn quên set secret trên cloud — và bạn
    chỉ phát hiện ra khi ai đó đã gọi API miễn phí bằng khóa mặc định đó.
    Không mặc định = fail fast ngay lúc khởi động.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # TODO (CP1): khai báo 6 trường theo bảng trên, ví dụ:
    #     port: int = 8000
    #     agent_api_key: str

    port: int = 8000
    agent_api_key: str
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_minute: int = 10
    monthly_budget_usd: float = 10.0
    log_level: str = "INFO"
    llm_provider: str = "mock"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = 60.0
    deepseek_max_tokens: int = 1024
    deepseek_input_price_per_million: float = 0.15
    deepseek_input_cache_price_per_million: float = 0.003
    deepseek_output_price_per_million: float = 0.60
    # Optional dedicated keys for browser clients. The owner key stays private.
    agent_api_keys: dict[str, str] = Field(default_factory=dict)
    global_monthly_budget_usd: float = 50.0
    strict_api_identity: bool = False

    @field_validator("agent_api_keys")
    @classmethod
    def validate_client_keys(cls, value: dict[str, str]) -> dict[str, str]:
        import re

        if len(value) > 100 or len(set(value.values())) != len(value):
            raise ValueError("client API keys must be unique (maximum 100)")
        if any(name == "owner" or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) or len(key) < 32 for name, key in value.items()):
            raise ValueError("invalid client identity or API key shorter than 32 characters")
        return value

    @model_validator(mode="after")
    def validate_master_key(self) -> "Settings":
        if self.agent_api_key in self.agent_api_keys.values():
            raise ValueError("owner key must differ from client keys")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Đọc cấu hình một lần rồi cache lại (đọc env mỗi request là lãng phí)."""
    return Settings()
