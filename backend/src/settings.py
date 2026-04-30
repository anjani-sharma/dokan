from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://ananta:ananta@localhost:5432/shopdb"

    # AI APIs
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    shop_chat_id: str = ""

    # App
    app_base_url: str = ""          # e.g. https://ananta.onrender.com  (no trailing slash)
    images_dir: str = "/tmp/ananta_images"
    timezone: str = "Asia/Kolkata"
    shop_name: str = "My Shop"

    # Cloudflare R2 (optional — falls back to local storage if not set)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""         # e.g. https://pub-xxxx.r2.dev  (your public bucket URL)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
