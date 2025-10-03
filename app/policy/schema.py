"""Strict schema for the Watcher policy file."""

from __future__ import annotations

from datetime import datetime, time
from ipaddress import ip_network
from pathlib import Path
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

    @field_validator("domain", "scope")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("domain and scope must be non-empty")
        return cleaned


class NetworkBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bandwidth_mb: int = Field(ge=0)
    time_budget_minutes: int = Field(ge=0)


class NetworkWindow(BaseModel):
    """Network access configuration for a set of CIDR ranges."""

    model_config = ConfigDict(extra="forbid")

    cidrs: list[str] = Field(min_length=1)
    windows: list[TimeWindow] = Field(min_length=1)

    @field_validator("cidrs")
    @classmethod
    def _validate_cidrs(cls, value: list[str]) -> list[str]:
        normalised: list[str] = []
        for raw in value:
            try:
                network = ip_network(raw, strict=False)
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError(f"invalid CIDR range: {raw!r}") from exc
            normalised.append(network.with_prefixlen)
        return normalised


class NetworkSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_windows: list[NetworkWindow] = Field(min_length=1)
    allowlist: list[DomainRule] = Field(default_factory=list)
    budgets: NetworkBudget


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    generated_at: datetime


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offline_default: bool = True
    require_consent: bool = True
    require_corroboration: bool = True
    kill_switch_file: str | None = None

    @field_validator("kill_switch_file")
    @classmethod
    def _validate_kill_switch(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("kill_switch_file must be an absolute path")
        return str(path)


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

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64:
            raise ValueError("sha256 must be 64 hexadecimal characters")
        try:
            int(cleaned, 16)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("sha256 must be hexadecimal") from exc
        return cleaned


class ModelsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: ModelEntry
    embedding: ModelEntry


class Policy(BaseModel):
    """Top level schema for ``policy.yaml``."""

    model_config = ConfigDict(extra="forbid")

    version: int
    autostart: bool
    subject: Subject
    defaults: Defaults
    network: NetworkSection
    budgets: Budgets
    categories: Categories
    models: ModelsSection

    def to_dict(self) -> dict[str, Any]:
        """Serialise the policy into a JSON-compatible dictionary."""

        return self.model_dump(mode="python")

