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
        "env_file": f".env.{os.getenv('APP_ENV', 'dev')}",
        "env_file_encoding": "utf-8",
    }


def get_settings() -> Settings:
    return Settings()
