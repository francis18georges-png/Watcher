"""Plugin protocol and discovery helpers."""

from __future__ import annotations

import importlib
import logging
from importlib import resources
from importlib.metadata import EntryPoint, entry_points
from importlib.resources.abc import Traversable
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


def _valid_plugin(obj: object) -> bool:
    """Return ``True`` when *obj* implements the :class:`Plugin` protocol."""

    return hasattr(obj, "name") and callable(getattr(obj, "run", None))


def discover_entry_point_plugins(group: str = "watcher.plugins") -> list[Plugin]:
    """Discover plugins registered via ``importlib.metadata`` entry points.

    Parameters
    ----------
    group:
        Groupe d'entry points à inspecter. Par défaut ``"watcher.plugins"``.
    """

    plugins: list[Plugin] = []
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
            plugin: Plugin = cls()
            if _valid_plugin(plugin):
                plugins.append(plugin)
            else:
                logging.warning("Invalid plugin %s", getattr(ep, "name", "<unknown>"))
        except Exception:  # pragma: no cover - best effort
            logging.exception(
                "Failed to load entry point %s", getattr(ep, "name", "<unknown>")
            )
    return plugins


Location = Path | Traversable


def _default_manifest() -> Traversable:
    """Return the plugin manifest bundled with the :mod:`app` package."""

    return resources.files("app").joinpath("plugins.toml")


def _resolve_manifest(base: Location | None) -> Location | None:
    """Return the manifest file corresponding to *base*.

    ``base`` may designate either a directory containing ``plugins.toml`` or the
    manifest file itself.  When ``None`` the manifest embedded in the ``app``
    package is returned.  ``None`` is returned when no manifest could be
    located.
    """

    if base is None:
        manifest = _default_manifest()
    elif isinstance(base, Traversable):
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


def reload_plugins(base: Location | None = None) -> list[Plugin]:
    """Load plugin instances defined in ``plugins.toml``.

    Parameters
    ----------
    base:
        Optional base directory containing the ``plugins.toml`` file.  When
        ``None`` the manifest embedded in :mod:`app` is used.
    """

    manifest = _resolve_manifest(base if base is not None else _default_manifest())
    plugins: list[Plugin] = []
    if manifest is not None:
        try:
            data = tomllib.loads(_read_manifest(manifest))
        except Exception:  # pragma: no cover - best effort
            logging.exception("Invalid plugins.toml")
        else:
            for item in data.get("plugins", []):
                path = item.get("path")
                if not path:
                    continue
                module_name, _, class_name = path.partition(":")
                try:
                    module = importlib.import_module(module_name)
                    cls = getattr(module, class_name)
                    plugin: Plugin = cls()
                    if _valid_plugin(plugin):
                        plugins.append(plugin)
                    else:
                        logging.warning("Invalid plugin %s", path)
                except Exception:  # pragma: no cover - best effort
                    logging.exception("Failed to load plugin %s", path)

    plugins.extend(discover_entry_point_plugins())
    return plugins


__all__ = ["Plugin", "reload_plugins", "discover_entry_point_plugins"]
