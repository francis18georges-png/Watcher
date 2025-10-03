"""Strict schema for the Watcher policy file."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_window(value: str) -> tuple[time, time]:
    try:
        start_raw, end_raw = value.split("-", 1)
        start = time.fromisoformat(start_raw)
        end = time.fromisoformat(end_raw)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"invalid window specification: {value!r}") from exc
    if start >= end:
        raise ValueError("time window must end after it starts")
    return start, end


class TimeWindow(BaseModel):
    """Allowed network window."""

    model_config = ConfigDict(extra="forbid")

    days: list[str] = Field(min_length=1)
    window: str

    @field_validator("days")
    @classmethod
    def _normalise_days(cls, value: list[str]) -> list[str]:
        allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        normalised = [item.lower() for item in value]
        invalid = sorted(set(normalised) - allowed)
        if invalid:
            raise ValueError(f"invalid days: {', '.join(invalid)}")
        return normalised

    @field_validator("window")
    @classmethod
    def _validate_window(cls, value: str) -> str:
        _parse_window(value)
        return value


class DomainRule(BaseModel):
    """Policy entry describing a domain that is allowed for scraping."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    categories: list[str] = Field(default_factory=list)
    bandwidth_mb: int = Field(ge=0, default=0)
    time_budget_minutes: int = Field(ge=0, default=0)
    allow_subdomains: bool = True
    scope: str = "web"
    last_approved: datetime | None = None


class NetworkSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_windows: list[TimeWindow]
    allowlist: list[DomainRule] = Field(default_factory=list)
    bandwidth_mb: int = Field(ge=0)
    time_budget_minutes: int = Field(ge=0)


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    generated_at: datetime


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offline: bool = True
    require_consent: bool = True
    kill_switch: bool = False


class Budgets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_percent: int = Field(ge=0, le=100)
    ram_mb: int = Field(ge=0)


class Categories(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: list[str] = Field(default_factory=list)


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sha256: str
    license: str


class ModelsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: ModelEntry
    embedding: ModelEntry


class Policy(BaseModel):
    """Top level schema for ``policy.yaml``."""

    model_config = ConfigDict(extra="forbid")

    version: int
    subject: Subject
    defaults: Defaults
    network: NetworkSection
    budgets: Budgets
    categories: Categories
    models: ModelsSection

    def to_dict(self) -> dict[str, Any]:
        """Serialise the policy into a JSON-compatible dictionary."""

        return self.model_dump(mode="python")

