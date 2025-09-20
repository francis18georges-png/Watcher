"""Central configuration factory based on ``pydantic-settings``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import logging
import os
import tomllib

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.configuration import (
    CriticSettings,
    DataSettings,
    DatasetSettings,
    DevSettings,
    EmbeddingsSettings,
    IntelligenceSettings,
    LLMSettings,
    LearningSettings,
    MemorySettings,
    ModelSettings,
    PathsSettings,
    PlannerSettings,
    SandboxSettings,
    ScraperSettings,
    TrainingSettings,
    UISettings,
)


logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent
_ENV_CACHE: dict[str, str] | None = None
_EXPLICIT_ENVIRONMENT: str | None = None


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", path)
        raise
    except tomllib.TOMLDecodeError as exc:
        logger.error("Invalid TOML in %s: %s", path, exc)
        raise


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _parse_env_file() -> dict[str, str]:
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE

    env_path = _CONFIG_DIR.parent / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    _ENV_CACHE = values
    return values


def _resolve_environment_name() -> str | None:
    if _EXPLICIT_ENVIRONMENT:
        return _EXPLICIT_ENVIRONMENT

    env = os.getenv("WATCHER_ENV") or os.getenv("WATCHER_PROFILE")
    if env:
        return env

    env_file = _parse_env_file()
    return env_file.get("WATCHER_ENV") or env_file.get("WATCHER_PROFILE")


class _TomlSettingsSource(PydanticBaseSettingsSource):
    """Settings source reading ``settings.toml`` and optional profile overrides."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)

    def __call__(self) -> dict[str, Any]:
        base_path = _CONFIG_DIR / "settings.toml"
        data = _read_toml(base_path)

        env_name = _resolve_environment_name()
        if env_name:
            profile_path = _CONFIG_DIR / f"settings.{env_name}.toml"
            if profile_path.exists():
                env_data = _read_toml(profile_path)
                data = _deep_merge(data, env_data)
            else:
                logger.warning(
                    "Profile configuration file not found: %s", profile_path
                )
        return data


class Settings(BaseSettings):
    """Typed configuration object backed by ``pydantic-settings``."""

    model_config = SettingsConfigDict(
        env_prefix="WATCHER_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    paths: PathsSettings = Field(default_factory=PathsSettings)
    ui: UISettings = Field(default_factory=UISettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    dev: DevSettings = Field(default_factory=DevSettings)
    planner: PlannerSettings = Field(default_factory=PlannerSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    learn: LearningSettings = Field(default_factory=LearningSettings)
    intelligence: IntelligenceSettings = Field(default_factory=IntelligenceSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    training: TrainingSettings = Field(default_factory=TrainingSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    dataset: DatasetSettings = Field(default_factory=DatasetSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    critic: CriticSettings = Field(default_factory=CriticSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            _TomlSettingsSource(settings_cls),
        )


@lru_cache(maxsize=None)
def get_settings(environment: str | None = None) -> Settings:
    """Return cached application settings, optionally for *environment*."""

    global _EXPLICIT_ENVIRONMENT
    previous = _EXPLICIT_ENVIRONMENT
    try:
        _EXPLICIT_ENVIRONMENT = environment
        return Settings()
    finally:
        _EXPLICIT_ENVIRONMENT = previous


def clear_settings_cache() -> None:
    """Clear the cached :class:`Settings` instance."""

    get_settings.cache_clear()


__all__ = [
    "Settings",
    "clear_settings_cache",
    "get_settings",
    "_read_toml",
]
