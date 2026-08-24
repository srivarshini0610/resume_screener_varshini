import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory pointing to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "resume_screener_db"

    # Google Gemini AI Configuration (Single Source of Truth)
    GEMINI_API_KEY: Optional[str] = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"

    # Legacy fields (kept for backward compatibility with older test scripts)
    HF_TOKEN: Optional[str] = ""
    HF_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def DATABASE_URL(self) -> str:
        """
        Construct the SQLAlchemy MySQL connection string.
        Format: mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST:DB_PORT/DB_NAME
        """
        if self.DB_PASSWORD:
            encoded_password = quote_plus(self.DB_PASSWORD)
            return f"mysql+pymysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return f"mysql+pymysql://{self.DB_USER}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
