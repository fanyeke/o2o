from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "coupon-decision-agent"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = "postgresql+psycopg2://coupon_user:coupon_pass@postgres:5432/coupon_agent"
    redis_url: str = "redis://redis:6379/0"

    llm_api_key: str = ""
    llm_model: str = "gpt-4"

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
