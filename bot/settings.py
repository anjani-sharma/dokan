from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    shop_chat_id: str
    backend_url: str = "http://localhost:8000"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    voice_language: str = "hi"   # whisper language hint: "hi" for Hindi, "en" for English
    images_dir: str = "/tmp/ananta_images"

    # Cloudflare R2 (optional — falls back to local path if not set)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
