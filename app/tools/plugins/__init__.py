"""Plugin protocol and discovery helpers."""

from __future__ import annotations

import importlib
import hashlib
import hmac
import logging
from dataclasses import dataclass
from importlib import resources
from importlib.metadata import EntryPoint, entry_points
from importlib.resources.abc import Traversable
from importlib.util import find_spec
from pathlib import Path
from typing import Iterable, Protocol

import tomllib


class Plugin(Protocol):
    """Interface commune à toutes les extensions Watcher.

    Chaque plugin doit fournir un identifiant court exposé via l'attribut
    :attr:`name` et implémenter la méthode :meth:`run` qui retourne un message
    lisible indiquant le résultat de son exécution.
    """

    #: Nom unique du plugin utilisé pour l'affichage et les logs.
    name: str

    def run(self) -> str:  # pragma: no cover - interface definition
        """Exécuter le plugin et retourner un message utilisateur."""
        ...


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """Information about a validated plugin entry.

    Attributes
    ----------
    name:
        Human readable identifier exposed by the plugin.
    module:
        Dotted path of the module defining the plugin class.
    attribute:
        Attribute path inside :attr:`module` pointing to the plugin class.
    api_version:
        Declared API version supported by the plugin manifest.
    signature:
        Expected SHA-256 digest of the plugin module.
    origin:
        Source of the plugin definition, e.g. ``"manifest"`` or
        ``"entry_point"``.
    """

    name: str
    module: str
    attribute: str
    api_version: str
    signature: str
    origin: str = "manifest"

    @property
    def import_path(self) -> str:
        """Return ``"module:attribute"`` path for convenience."""

        return f"{self.module}:{self.attribute}"


SUPPORTED_PLUGIN_API_VERSION = "1.0"


def _valid_plugin(obj: object) -> bool:
    """Return ``True`` when *obj* implements the :class:`Plugin` protocol."""

    return hasattr(obj, "name") and callable(getattr(obj, "run", None))


def _resolve_attribute(module: object, attribute: str) -> object:
    """Resolve ``attribute`` inside ``module`` supporting dotted paths."""

    obj = module
    for part in attribute.split("."):
        obj = getattr(obj, part)
    return obj


def compute_module_signature(module_name: str) -> str | None:
    """Return the SHA-256 digest of *module_name*'s source file."""

    spec = find_spec(module_name)
    if spec is None or spec.origin in {None, "built-in", "frozen"}:
        return None
    path = Path(spec.origin)
    try:
        data = path.read_bytes()
    except OSError:
        logging.debug(
            "Failed to read module %s for signature", module_name, exc_info=True
        )
        return None
    return hashlib.sha256(data).hexdigest()


def discover_entry_point_plugins(group: str = "watcher.plugins") -> list[LoadedPlugin]:
    """Discover plugins registered via ``importlib.metadata`` entry points.

    Parameters
    ----------
    group:
        Groupe d'entry points à inspecter. Par défaut ``"watcher.plugins"``.
    """

    plugins: list[LoadedPlugin] = []
    try:
        try:
            eps: Iterable[EntryPoint] = entry_points(group=group)
        except TypeError:  # pragma: no cover - fallback for older Python
            eps = [ep for ep in entry_points() if getattr(ep, "group", None) == group]
    except Exception:  # pragma: no cover - best effort
        logging.exception("Failed to query entry points")
        return plugins

    for ep in eps:
        try:
            cls = ep.load()
            plugin_obj = cls()
            if not _valid_plugin(plugin_obj):
                logging.warning(
                    "Invalid plugin %s", getattr(ep, "name", "<unknown>")
                )
                continue

            module_name = cls.__module__
            attribute = cls.__qualname__
            if "<locals>" in attribute:
                attribute = cls.__name__

            declared_version = (
                getattr(plugin_obj, "api_version", None)
                or getattr(cls, "api_version", None)
                or getattr(cls, "API_VERSION", None)
            )
            if declared_version != SUPPORTED_PLUGIN_API_VERSION:
                logging.warning(
                    "Plugin %s declares incompatible api_version %s",
                    getattr(plugin_obj, "name", module_name),
                    declared_version,
                )
                continue

            declared_signature = (
                getattr(plugin_obj, "signature", None)
                or getattr(cls, "signature", None)
                or getattr(cls, "SIGNATURE", None)
            )
            if not declared_signature:
                logging.warning(
                    "Plugin %s missing required signature", getattr(ep, "name", "")
                )
                continue

            actual_signature = compute_module_signature(module_name)
            if actual_signature is None or not hmac.compare_digest(
                declared_signature, actual_signature
            ):
                logging.error(
                    "Signature mismatch for plugin %s", getattr(ep, "name", "")
                )
                continue

            plugins.append(
                LoadedPlugin(
                    name=getattr(plugin_obj, "name"),
                    module=module_name,
                    attribute=attribute,
                    api_version=SUPPORTED_PLUGIN_API_VERSION,
                    signature=declared_signature,
                    origin="entry_point",
                )
            )
        except Exception:  # pragma: no cover - best effort
            logging.exception(
                "Failed to load entry point %s", getattr(ep, "name", "<unknown>")
            )
    return plugins


Location = Path | Traversable


def _resolve_manifest(base: Location | None) -> Location | None:
    """Return the manifest file corresponding to *base*.

    ``base`` may designate either a directory containing ``plugins.toml`` or the
    manifest file itself.  When ``None`` the manifest embedded in the ``app``
    package is returned.  ``None`` is returned when no manifest could be
    located.
    """

    if base is None:
        base = resources.files("app")

    if isinstance(base, Traversable):
        manifest = base if base.is_file() else base.joinpath("plugins.toml")
    else:
        base_path = Path(base)
        manifest = base_path if base_path.is_file() else base_path / "plugins.toml"

    if isinstance(manifest, Traversable):
        if not manifest.is_file():
            return None
        return manifest

    if not manifest.exists():
        return None
    return manifest


def _read_manifest(manifest: Location) -> str:
    if isinstance(manifest, Traversable):
        return manifest.read_text(encoding="utf-8")
    return manifest.read_text(encoding="utf-8")


def reload_plugins(base: Location | None = None) -> list[LoadedPlugin]:
    """Load plugin instances defined in ``plugins.toml``.

    Parameters
    ----------
    base:
        Optional base directory containing the ``plugins.toml`` file.  When
        ``None`` the manifest embedded in :mod:`app` is used.
    """

    manifest = _resolve_manifest(base)
    plugins: list[LoadedPlugin] = []
    if manifest is not None:
        try:
            data = tomllib.loads(_read_manifest(manifest))
        except Exception:  # pragma: no cover - best effort
            logging.exception("Invalid plugins.toml")
        else:
            for item in data.get("plugins", []):
                path = item.get("path")
                api_version = item.get("api_version")
                signature = item.get("signature")
                if not path or not api_version or not signature:
                    logging.warning(
                        "Incomplete plugin definition in manifest: %s", item
                    )
                    continue

                if api_version != SUPPORTED_PLUGIN_API_VERSION:
                    logging.warning(
                        "Plugin %s declares unsupported api_version %s",
                        path,
                        api_version,
                    )
                    continue

                module_name, _, attribute = path.partition(":")
                if not module_name or not attribute:
                    logging.warning("Invalid plugin path %s", path)
                    continue

                actual_signature = compute_module_signature(module_name)
                if actual_signature is None:
                    logging.error("Unable to compute signature for %s", module_name)
                    continue
                if not hmac.compare_digest(signature, actual_signature):
                    logging.error("Signature mismatch for plugin %s", path)
                    continue

                try:
                    module = importlib.import_module(module_name)
                    cls = _resolve_attribute(module, attribute)
                    plugin_obj = cls()
                except Exception:  # pragma: no cover - best effort
                    logging.exception("Failed to load plugin %s", path)
                    continue

                if not _valid_plugin(plugin_obj):
                    logging.warning("Invalid plugin %s", path)
                    continue

                plugins.append(
                    LoadedPlugin(
                        name=getattr(plugin_obj, "name"),
                        module=module_name,
                        attribute=attribute,
                        api_version=api_version,
                        signature=signature,
                        origin="manifest",
                    )
                )

    plugins.extend(discover_entry_point_plugins())
    return plugins


__all__ = [
    "Plugin",
    "LoadedPlugin",
    "SUPPORTED_PLUGIN_API_VERSION",
    "compute_module_signature",
    "reload_plugins",
    "discover_entry_point_plugins",
]
