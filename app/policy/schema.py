"""Strict schema for the Watcher policy file."""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class DailyWindow(BaseModel):
    """Allowed network window for a single day."""

    model_config = ConfigDict(extra="forbid")

    start: time
    end: time

    @model_validator(mode="after")
    def _validate_bounds(self) -> DailyWindow:  # pragma: no cover - exercised via Policy
        if self.start >= self.end:
            raise ValueError("time window must end after it starts")
        return self


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


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    generated_at: datetime


class Budgets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bandwidth_mb_per_day: int = Field(ge=0)
    cpu_percent_cap: int = Field(ge=0, le=100)
    ram_mb_cap: int = Field(ge=0)


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
    autostart: bool
    offline_default: bool
    network_windows: dict[str, DailyWindow]
    budgets: Budgets
    allowlist_domains: list[DomainRule] = Field(default_factory=list)
    categories: Categories
    models: ModelsSection
    require_consent: bool = True
    require_corroboration: int = Field(ge=2)
    kill_switch_file: Path

    def to_dict(self) -> dict[str, Any]:
        """Serialise the policy into a JSON-compatible dictionary."""

        data = self.model_dump(mode="python")
        windows = {
            day: {"start": window.start.strftime("%H:%M"), "end": window.end.strftime("%H:%M")}
            for day, window in self.network_windows.items()
        }
        data["network_windows"] = windows
        data["kill_switch_file"] = str(self.kill_switch_file)
        return data

    @field_validator("network_windows")
    @classmethod
    def _normalise_windows(
        cls, value: dict[str, DailyWindow]
    ) -> dict[str, DailyWindow]:
        if not value:
            raise ValueError("network_windows must define at least one day")
        normalised: dict[str, DailyWindow] = {}
        for key, window in value.items():
            alias = key.strip().lower()
            if alias not in _DAYS:
                raise ValueError(f"invalid day name: {key!r}")
            normalised[alias] = window
        return normalised

