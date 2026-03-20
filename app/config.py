from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # WooCommerce
    wc_site_url: str = ""
    wc_consumer_key: str = ""
    wc_consumer_secret: str = ""
    wc_webhook_secret: str = ""

    # Meta WhatsApp Cloud API
    meta_phone_number_id: str = ""
    meta_whatsapp_token: str = ""
    meta_verify_token: str = ""

    # Statuts WooCommerce
    wc_status_confirmed: str = "processing"
    wc_status_cancelled: str = "cancelled"
    auto_cancel_hours: int = 24
    anthropic_api_key: str = ""


    # App
    secret_key: str = "dev-secret"
    database_url: str = "sqlite:///./agent.db"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
