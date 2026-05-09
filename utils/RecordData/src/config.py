from pydantic_settings import BaseSettings, SettingsConfigDict
import os
class Settings(BaseSettings):
    APP_ENV: str = "development"
    RAW_DATA_DIR: str = "./data/raw"
    MERGED_DATA_DIR: str = "/data/merged"
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_GROUP_ID: str
    KAFKA_TOPIC: str
    AUTO_COMMIT: bool = True
    AUTO_OFFSET_RESET: str = "latest"
    model_config = SettingsConfigDict(
        env_file="./.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
settings = Settings()