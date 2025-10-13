"""Strict schema for the Watcher policy file."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DAY_ORDER: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_DAY_ALIASES: dict[str, str] = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
    "mon": "mon",
    "tue": "tue",
    "wed": "wed",
    "thu": "thu",
    "fri": "fri",
    "sat": "sat",
    "sun": "sun",
}


def _normalise_day(value: str) -> str:
    key = value.strip().lower()
    if key in {"mon-sun", "mon-sun."}:
        return "mon-sun"
    alias = _DAY_ALIASES.get(key)
    if alias:
        return alias
    if key not in _DAY_ALIASES:
        raise ValueError(f"invalid day: {value!r}")
    return _DAY_ALIASES[key]


def _expand_range(start: str, end: str) -> list[str]:
    start_key = _DAY_ALIASES.get(start.strip().lower(), start.strip().lower())
    end_key = _DAY_ALIASES.get(end.strip().lower(), end.strip().lower())
    if start_key not in _DAY_ORDER or end_key not in _DAY_ORDER:
        raise ValueError(f"invalid day range: {start!r}-{end!r}")
    start_index = _DAY_ORDER.index(start_key)
    end_index = _DAY_ORDER.index(end_key)
    if start_index > end_index:
        raise ValueError("day ranges must be ascending")
    return list(_DAY_ORDER[start_index : end_index + 1])


def _format_time(value: time) -> str:
    return value.strftime("%H:%M")


class NetworkWindow(BaseModel):
    """Allowed network window."""

    model_config = ConfigDict(extra="forbid")

    days: list[str]
    start: time
    end: time

    @field_validator("days", mode="before")
    @classmethod
    def _coerce_days(cls, value: Iterable[str] | str) -> list[str]:
        if isinstance(value, str):
            raw_values = [value]
        else:
            raw_values = list(value)
        expanded: list[str] = []
        for item in raw_values:
            text = str(item).strip()
            if not text:
                continue
            if "-" in text and text.count("-") == 1 and len(text) >= 3:
                start, end = text.split("-", 1)
                expanded.extend(_expand_range(start, end))
                continue
            if text.lower() == "mon-sun":
                expanded.extend(_DAY_ORDER)
                continue
            expanded.append(text)
        normalised = []
        for item in expanded:
            if item.lower() == "mon-sun":
                normalised.extend(_DAY_ORDER)
            else:
                normalised.append(_normalise_day(item))
        if not normalised:
            raise ValueError("at least one day must be provided")
        return sorted(set(normalised), key=_DAY_ORDER.index)

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse_time(cls, value: Any) -> time:
        if isinstance(value, time):
            return value
        try:
            return time.fromisoformat(str(value))
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"invalid time specification: {value!r}") from exc

    @model_validator(mode="after")
    def _validate_range(self) -> "NetworkWindow":
        if self.start >= self.end:
            raise ValueError("time window must end after it starts")
        return self

    def duration_minutes(self) -> int:
        start_minutes = self.start.hour * 60 + self.start.minute
        end_minutes = self.end.hour * 60 + self.end.minute
        return end_minutes - start_minutes

    def to_dict(self) -> dict[str, Any]:
        return {
            "days": list(self.days),
            "start": _format_time(self.start),
            "end": _format_time(self.end),
        }


class Budgets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bandwidth_mb_per_day: int = Field(ge=0)
    cpu_percent_cap: int = Field(ge=0, le=100)
    ram_mb_cap: int = Field(ge=0)

    def to_dict(self) -> dict[str, int]:
        return self.model_dump(mode="python")


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="python")
        payload["generated_at"] = payload["generated_at"].isoformat()
        return payload


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sha256: str
    license: str

    def to_dict(self) -> dict[str, str]:
        return self.model_dump(mode="python")


class ModelsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: ModelEntry
    embedding: ModelEntry

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm": self.llm.to_dict(),
            "embedding": self.embedding.to_dict(),
        }


@dataclass(slots=True)
class DomainRule:
    """Policy entry describing a domain that is allowed for scraping."""

    domain: str
    bandwidth_mb: int
    time_budget_minutes: int
    scope: str = "web"


class Policy(BaseModel):
    """Top level schema for ``policy.yaml``."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1, default=1)
    autostart: bool = True
    offline_default: bool = True
    require_corroboration: int = Field(ge=1, default=2)
    kill_switch_file: str = Field(default="~/.watcher/disable")
    network_windows: list[NetworkWindow]
    budgets: Budgets
    allowlist_domains: list[str] = Field(default_factory=list)
    subject: Subject | None = None
    models: ModelsSection

    @field_validator("allowlist_domains", mode="before")
    @classmethod
    def _coerce_domains(cls, value: Iterable[str]) -> list[str]:
        domains = []
        for item in value or []:
            text = str(item).strip().lower()
            if text:
                domains.append(text)
        return sorted(set(domains))

    @model_validator(mode="after")
    def _validate_windows(self) -> "Policy":
        if not self.network_windows:
            raise ValueError("at least one network window must be defined")
        return self

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "version": self.version,
            "autostart": self.autostart,
            "offline_default": self.offline_default,
            "require_corroboration": self.require_corroboration,
            "kill_switch_file": self.kill_switch_file,
            "network_windows": [window.to_dict() for window in self.network_windows],
            "budgets": self.budgets.to_dict(),
            "allowlist_domains": list(self.allowlist_domains),
            "models": self.models.to_dict(),
        }
        if self.subject is not None:
            payload["subject"] = self.subject.to_dict()
        return payload

    def kill_switch_path(self, *, home: Path | None = None) -> Path:
        raw = Path(self.kill_switch_file).expanduser()
        if raw.is_absolute():
            return raw
        base = Path.home() if home is None else home
        return (base / raw).expanduser()

    def window_duration_minutes(self) -> int:
        return max(window.duration_minutes() for window in self.network_windows)

    def domain_rules(self) -> list[DomainRule]:
        default_bandwidth = self.budgets.bandwidth_mb_per_day
        time_budget = self.window_duration_minutes()
        return [
            DomainRule(domain=domain, bandwidth_mb=default_bandwidth, time_budget_minutes=time_budget)
            for domain in self.allowlist_domains
        ]

    def kill_switch_engaged(self, *, home: Path | None = None) -> bool:
        return self.kill_switch_path(home=home).exists()

    def to_persistable(self) -> dict[str, Any]:
        return self.to_dict()


__all__ = [
    "Budgets",
    "DomainRule",
    "ModelEntry",
    "ModelsSection",
    "NetworkWindow",
    "Policy",
    "Subject",
]
