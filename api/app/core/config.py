from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://cha3535:cha3535@localhost:5432/cha3535"
    redis_url: str = "redis://localhost:6379/0"

    jwt_private_key: str = ""
    jwt_public_key: str = ""
    admin_jwt_secret: str = "change-me-admin-secret"
    access_token_ttl_minutes: int = 15
    admin_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    refresh_cookie_name: str = "cha_refresh_token"
    cookie_secure: bool = True
    bcrypt_rounds: int = 12

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_vip_price_id: str = ""
    stripe_black_price_id: str = ""
    stripe_elite_price_id: str = ""
    stripe_diamond_price_id: str = ""
    checkout_success_url: str = "https://app.cha3535.com/billing/success"
    checkout_cancel_url: str = "https://app.cha3535.com/billing/cancel"
    portal_return_url: str = "https://app.cha3535.com/account"
    trial_days: int = 7

    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "cha3535-avatars"
    storage_backend: str = "s3"
    local_media_dir: str = "./media"
    avatar_url_ttl_seconds: int = 3600

    sentry_dsn: str = ""
    datadog_api_key: str = ""
    cors_origins: str = "https://app.cha3535.com,https://admin.cha3535.com"
    rate_limit_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def stripe_price_ids(self) -> dict[str, str]:
        return {
            "vip": self.stripe_vip_price_id,
            "black": self.stripe_black_price_id,
            "elite": self.stripe_elite_price_id,
            "diamond": self.stripe_diamond_price_id,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
