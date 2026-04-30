from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ananta:ananta@localhost:5432/shopdb"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    telegram_bot_token: str = ""
    shop_chat_id: str = ""
    images_dir: str = "/app/images"
    timezone: str = "Asia/Kolkata"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
