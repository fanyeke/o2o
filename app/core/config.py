from pydantic_settings import BaseSettings
from pydantic import model_validator
from pathlib import Path
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

    # Rules configuration directory (relative path or absolute)
    rules_dir: str = "config/rules"

    model_config = {
        "env_file": ".env.test" if os.getenv("APP_ENV") == "test" else ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore extra env vars
    }

    @model_validator(mode="after")
    def validate_critical_config(self) -> "Settings":
        """Validate critical configuration after initialization.

        In production environment (app_env == 'prod'), missing critical
        configurations will raise an error to prevent insecure deployments.
        In development, warnings are issued instead.
        """
        is_production = self.app_env == "prod"

        # Validate API Token
        if not self.api_token:
            if is_production:
                raise ValueError(
                    "API_TOKEN is required in production environment. "
                    "Set the API_TOKEN environment variable."
                )
            else:
                import warnings
                warnings.warn(
                    "API_TOKEN not configured. Protected endpoints will reject requests.",
                    UserWarning
                )

        # Validate LLM API Key
        if not self.llm_api_key:
            if is_production:
                raise ValueError(
                    "LLM_API_KEY is required in production environment. "
                    "Set the LLM_API_KEY environment variable."
                )
            else:
                import warnings
                warnings.warn(
                    "LLM_API_KEY not configured. Agent decision service will fail.",
                    UserWarning
                )

        # Validate Feishu verification token in production
        if is_production and not self.feishu_verification_token:
            raise ValueError(
                "FEISHU_VERIFICATION_TOKEN is required in production environment. "
                "Set the FEISHU_VERIFICATION_TOKEN environment variable."
            )

        return self

    def get_rules_dir(self) -> Path:
        """Get the rules directory as an absolute path.

        Returns:
            Path object pointing to the rules directory.
            If rules_dir is relative, resolves relative to project root.
        """
        rules_path = Path(self.rules_dir)
        if rules_path.is_absolute():
            return rules_path

        # Resolve relative path from project root
        # Project root is the directory containing 'app' package
        project_root = Path(__file__).parent.parent.parent
        return project_root / self.rules_dir

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "prod"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "dev"


def get_settings() -> Settings:
    return Settings()
