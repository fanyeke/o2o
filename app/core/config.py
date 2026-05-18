from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "coupon-decision-agent"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = "postgresql+psycopg2://coupon_user:coupon_pass@postgres:5432/coupon_agent"
    redis_url: str = "redis://redis:6379/0"

    # DeepSeek LLM Configuration
    llm_api_key: str = ""  # DeepSeek API Key
    llm_model: str = "deepseek-v4-flash"  # Model name
    llm_endpoint: str = "https://api.deepseek.com/v1"  # API endpoint
    llm_timeout: int = 30  # Timeout in seconds
    llm_max_retries: int = 3  # Max retry attempts

    # Feishu Configuration
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""

    # API Token for protected endpoints
    api_token: str = ""  # API Token for authentication

    model_config = {
        "env_file": ".env",  # Unified .env file (not .env.dev)
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore extra env vars
    }

    def __post_init__(self):
        """Validate critical configuration after initialization."""
        if not self.api_token:
            import warnings
            warnings.warn(
                "API_TOKEN not configured. Protected endpoints will reject requests.",
                UserWarning
            )

        if not self.llm_api_key:
            import warnings
            warnings.warn(
                "LLM_API_KEY not configured. Agent decision service will fail.",
                UserWarning
            )


def get_settings() -> Settings:
    return Settings()
