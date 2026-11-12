"""Settings loaded from env (spec §6.3).

One Settings object constructed at the composition root and passed
down; no other module reads `os.environ`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrivacyMode(StrEnum):
    SYNTHETIC = "synthetic"
    HASH_ONLY = "hash_only"


class LlmProvider(StrEnum):
    FAKE = "fake"
    CASSETTE = "cassette"
    GEMINI = "gemini"
    GROQ = "groq"


class EmbedProvider(StrEnum):
    FAKE = "fake"
    GEMINI = "gemini"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WAGEGUARD_",
        env_file=".env",
        extra="ignore",
    )

    app_env: str = "dev"
    privacy_mode: PrivacyMode = PrivacyMode.SYNTHETIC

    llm_provider: LlmProvider = LlmProvider.FAKE
    llm_model_id: str = "gemini-flash-lite-latest"
    llm_timeout_seconds: int = 30
    llm_max_tokens: int = 1024

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    embedding_provider: EmbedProvider = EmbedProvider.FAKE
    embedding_model_id: str = "fake-test-v1"
    embedding_dimension: int = 8

    api_host: str = "127.0.0.1"
    api_port: int = 8080
    api_keys: str = ""  # comma-separated "role:key" pairs

    log_level: str = "INFO"
    log_format: str = "json"

    ledger_path: str = ""  # empty -> in-memory; set path -> file-backed
