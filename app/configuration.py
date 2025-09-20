"""Typed configuration models for Watcher settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class SectionSettings(BaseSettings):
    """Base class for configuration sections.

    The settings are primarily populated from the top-level :class:`Settings`
    factory therefore environment lookups for the individual sections are
    disabled.  This avoids repeated environment parsing while still benefiting
    from Pydantic's validation when the sections are instantiated with data
    originating from ``settings.toml`` or environment overrides.
    """

    model_config = SettingsConfigDict(extra="ignore", validate_default=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Only use the data supplied by the parent :class:`Settings` instance so
        # nested sections do not parse the environment individually.
        return (init_settings,)


class PathsSettings(SectionSettings):
    """Filesystem locations used by the application."""

    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1],
        description="Absolute path to the project root.",
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory containing runtime data files.",
    )
    datasets_dir: Path = Field(
        default=Path("datasets"),
        description="Directory containing raw and processed datasets.",
    )
    memory_dir: Path = Field(
        default=Path("memory"),
        description="Directory for memory database and cache files.",
    )
    logs_dir: Path = Field(
        default=Path("logs"),
        description="Directory used to persist log files.",
    )

    def resolve(self, value: Path | str) -> Path:
        """Return an absolute path for ``value`` relative to :attr:`base_dir`."""

        path = Path(value)
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()


class UISettings(SectionSettings):
    """User interface configuration."""

    mode: str = Field(default="Sur", description="Mode d'affichage par défaut.")
    theme: str = Field(default="dark", description="Thème graphique préféré.")
    language: str = Field(default="fr", description="Langue de l'interface.")
    autosave: bool = Field(default=True, description="Active l'enregistrement automatique.")


class LLMSettings(SectionSettings):
    """Parameters for the local large language model backend."""

    backend: str = Field(default="ollama", description="Backend préféré pour le LLM.")
    model: str = Field(default="llama3.2:3b", description="Identifiant du modèle à utiliser.")
    host: str = Field(default="127.0.0.1:11434", description="Hôte du serveur Ollama.")
    ctx: int | None = Field(default=4096, description="Taille de fenêtre de contexte.")
    fallback_phrase: str = Field(default="Echo", description="Préfixe utilisé en mode secours.")

    @field_validator("backend", "model", "host", "fallback_phrase")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("ctx")
    @classmethod
    def _positive_ctx(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("ctx must be a positive integer")
        return value


class DevSettings(SectionSettings):
    """Developer focused options."""

    logging: str = Field(default="debug", description="Niveau de log par défaut.")
    trace_requests: bool = Field(default=False, description="Trace HTTP détaillée.")


class PlannerSettings(SectionSettings):
    """Planning defaults used by the assistant."""

    default_platform: str = Field(default="windows", description="Plateforme cible par défaut.")
    default_license: str = Field(default="MIT", description="Licence de projet par défaut.")


class MemorySettings(SectionSettings):
    """Vector memory and cache configuration."""

    db_path: Path = Field(default=Path("memory/mem.db"), description="Chemin vers la base mémoire.")
    cache_size: int = Field(default=128, description="Taille du cache LRU pour les réponses.")
    embed_model: str = Field(default="nomic-embed-text", description="Modèle d'embedding préféré.")
    embed_host: str = Field(default="127.0.0.1:11434", description="Hôte du service d'embedding.")
    summary_max_tokens: int = Field(default=512, description="Limite de tokens pour les résumés.")

    @field_validator("cache_size", "summary_max_tokens")
    @classmethod
    def _positive_int(cls, value: int) -> int:
        if value < 1:
            raise ValueError("value must be a positive integer")
        return value


class LearningSettings(SectionSettings):
    """Hyper-parameters for the learning loop."""

    optimizer: str = Field(default="adam")
    learning_rate: float = Field(default=0.1)
    reward_clip: float = Field(default=1.0)


class IntelligenceSettings(SectionSettings):
    """High level intelligence tuning parameters."""

    mode: str = Field(default="offline")
    curriculum: str = Field(default="default")


class DataSettings(SectionSettings):
    """Data pipeline configuration."""

    raw_dir: Path = Field(default=Path("datasets/raw"))
    processed_dir: Path = Field(default=Path("datasets/processed"))
    steps: Mapping[str, str] = Field(default_factory=dict, description="Etapes de pipeline déclarées.")


class TrainingSettings(SectionSettings):
    """Training hyper-parameters for ML components."""

    seed: int = Field(default=42)
    batch_size: int = Field(default=16)
    lr: float = Field(default=1e-4)

    @field_validator("batch_size")
    @classmethod
    def _positive_batch(cls, value: int) -> int:
        if value < 1:
            raise ValueError("batch_size must be positive")
        return value


class ModelSettings(SectionSettings):
    """Metadata describing the assistant model."""

    name: str = Field(default="watcher")
    revision: str = Field(default="0.1")
    precision: str = Field(default="fp16")


class ScraperSettings(SectionSettings):
    """Web scraping and rate limiting configuration."""

    rate_per_domain: float = Field(default=1.0)
    concurrency: int = Field(default=6)
    user_agent: str = Field(default="WatcherBot/1.0 (+https://github.com/francis18georges-png/Watcher)")

    @field_validator("rate_per_domain")
    @classmethod
    def _non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("rate_per_domain must be >= 0")
        return value

    @field_validator("concurrency")
    @classmethod
    def _positive_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("concurrency must be a positive integer")
        return value


class DatasetSettings(SectionSettings):
    """Dataset locations."""

    raw_dir: Path = Field(default=Path("datasets/raw"))
    processed_dir: Path = Field(default=Path("datasets/processed"))


class EmbeddingsSettings(SectionSettings):
    """Configuration for embedding backends."""

    backend: str = Field(default="local_faiss")


class SandboxSettings(SectionSettings):
    """Runtime sandbox limits for executing code."""

    cpu_seconds: int | None = Field(default=60, description="Quota CPU par processus.")
    memory_bytes: int | None = Field(
        default=256 * 1024 * 1024,
        description="Limite mémoire par processus en octets.",
        )
    timeout_seconds: float = Field(default=30.0, description="Timeout pour l'exécution sandbox.")

    @field_validator("cpu_seconds", "memory_bytes")
    @classmethod
    def _positive_optional(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("limit must be positive when provided")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def _positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        return value


class LoggingSettings(SectionSettings):
    """Structured logging configuration."""

    config_path: Path | None = Field(
        default=None,
        description="Chemin vers un fichier de configuration logging YAML ou JSON.",
    )
    fallback_level: str = Field(
        default="INFO",
        description="Niveau appliqué si aucun fichier de configuration n'est disponible.",
    )

    @field_validator("fallback_level")
    @classmethod
    def _valid_level(cls, value: str) -> str:
        if not value:
            raise ValueError("fallback_level must not be empty")
        level = value.upper()
        if not isinstance(getattr(logging, level, None), int):
            raise ValueError("fallback_level must reference a standard logging level")
        return level


class CriticSettings(SectionSettings):
    """Critic configuration used for heuristic feedback."""

    polite_keywords: tuple[str, ...] = Field(
        default=(
            "please",
            "thank you",
            "merci",
            "s'il vous plaît",
            "s'il vous plait",
            "bonjour",
            "salut",
        )
    )


__all__ = [
    "CriticSettings",
    "DataSettings",
    "DatasetSettings",
    "DevSettings",
    "EmbeddingsSettings",
    "LoggingSettings",
    "IntelligenceSettings",
    "LLMSettings",
    "LearningSettings",
    "MemorySettings",
    "ModelSettings",
    "PathsSettings",
    "PlannerSettings",
    "SandboxSettings",
    "ScraperSettings",
    "TrainingSettings",
    "UISettings",
]
