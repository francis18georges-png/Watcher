"""Model registry and download helpers for local-first deployments."""

from __future__ import annotations

import base64
import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(slots=True)
class ModelSpec:
    """Description of a downloadable model artifact."""

    name: str
    sha256: str
    size_bytes: int
    urls: Sequence[str]
    license: str
    family: str
    backend: str
    context_size: int
    description: str
    embedded_resource: str | None = None

    def destination(self, base_dir: Path) -> Path:
        return base_dir / self.name


class DownloadError(RuntimeError):
    """Raised when an artifact cannot be retrieved from any source."""


CHUNK_SIZE = 1 << 20


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _copy_embedded(resource: str, destination: Path) -> None:
    package_root = Path(__file__).resolve().parent.parent
    src = package_root / resource
    if not src.is_file():
        raise FileNotFoundError(f"Embedded model resource missing: {resource}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, destination)


def _download_once(url: str, destination: Path, resume: bool) -> bool:
    headers: dict[str, str] = {
        "User-Agent": "Watcher/1.0 (+https://github.com/francis18georges-png/Watcher)",
    }
    mode = "wb"
    existing = 0
    if resume and destination.exists():
        existing = destination.stat().st_size
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"
            mode = "ab"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status in {200, 206}:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open(mode) as fh:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        fh.write(chunk)
                return True
            return False
    except Exception:
        return False


def _artifact_matches_spec(path: Path, spec: ModelSpec) -> bool:
    """Return ``True`` when *path* matches the expected ``sha256`` and size."""

    if not path.exists():
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if spec.size_bytes > 0 and size != spec.size_bytes:
        return False
    return _hash_file(path) == spec.sha256


def download_model(spec: ModelSpec, target_dir: Path, resume: bool = True) -> Path:
    """Ensure the given model *spec* is available under *target_dir*.

    The function attempts each declared URL and supports download resumption.
    When all remote sources fail but an embedded fallback is available, that
    fallback is copied in place.  The resulting file is verified against the
    expected SHA-256 digest; mismatches raise :class:`DownloadError`.
    """

    destination = spec.destination(target_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if _artifact_matches_spec(destination, spec):
        return destination

    if destination.exists():
        destination.unlink(missing_ok=True)

    temp = destination.with_suffix(".part")
    if temp.exists() and not resume:
        temp.unlink()

    for url in spec.urls:
        if _download_once(url, temp, resume=resume):
            if _artifact_matches_spec(temp, spec):
                temp.replace(destination)
                return destination
            temp.unlink(missing_ok=True)

    if spec.embedded_resource is not None:
        _copy_embedded(spec.embedded_resource, destination)
        if _artifact_matches_spec(destination, spec):
            return destination
        destination.unlink(missing_ok=True)

    if temp.exists():
        temp.unlink(missing_ok=True)

    raise DownloadError(f"Unable to retrieve model {spec.name}")


def ensure_models(base_dir: Path, specs: Iterable[ModelSpec]) -> list[Path]:
    """Download all *specs* under *base_dir* and return their paths."""

    paths: list[Path] = []
    for spec in specs:
        paths.append(download_model(spec, base_dir))
    return paths


def _decode_embedded_hash(data: str) -> str:
    return base64.b64decode(data.encode("ascii"), validate=True).decode("ascii")


MODEL_REGISTRY: dict[str, list[ModelSpec]] = {
    "llm": [
        ModelSpec(
            name="demo-smollm-135m-instruct.Q4_K_M.gguf",
            sha256=_decode_embedded_hash(
                "NDNkMjgxOWZiNmJiOTRmNTE0ZjRmMDk5MjYzYjQ1MjZhNjUyOTNmZWU3ZmRjYmVjOGQzZjEyZGYwZDQ4NTI5Zg=="  # noqa: E501
            ),
            size_bytes=1048576,
            urls=(
                "https://huggingface.co/datasets/francisgg/demo-watch-llm/resolve/main/"
                "demo-smollm-135m-instruct.Q4_K_M.gguf"
            ).split(),
            license="Apache-2.0",
            family="smollm",
            backend="llama.cpp",
            context_size=4096,
            description=(
                "Modèle démonstration dérivé de SmolLM 135M quantifié Q4_K_M. "
                "Destiné aux tests offline deterministes."
            ),
            embedded_resource="assets/models/demo-smollm-135m-instruct.Q4_K_M.gguf",
        ),
    ],
    "embedding": [
        ModelSpec(
            name="demo-all-MiniLM-L6-v2.tar.gz",
            sha256=_decode_embedded_hash(
                "YTVhNTFiNTMzNjgxYTY5NDQ2MjgzZTNjNmNlN2MzNWJjMDk4ZTBiZDU0MGM5ZmY1NjkzMWEwMmM0MTRkYzA1NA=="  # noqa: E501
            ),
            size_bytes=262144,
            urls=(
                "https://huggingface.co/datasets/francisgg/demo-watch-llm/resolve/main/"
                "demo-all-MiniLM-L6-v2.tar.gz"
            ).split(),
            license="Apache-2.0",
            family="sentence-transformers",
            backend="sentence-transformers",
            context_size=512,
            description=(
                "Sous-ensemble de all-MiniLM-L6-v2 pour tests rapides. Fournit un "
                "vecteur fixe déterministe."
            ),
            embedded_resource="assets/models/demo-all-MiniLM-L6-v2.tar.gz",
        ),
    ],
}


def select_models(profile_threads: int, has_gpu: bool) -> dict[str, ModelSpec]:
    """Pick the best model specs for the detected hardware."""

    del has_gpu  # reserved for future use
    llm = MODEL_REGISTRY["llm"][0]
    emb = MODEL_REGISTRY["embedding"][0]
    return {"llm": llm, "embedding": emb}


__all__ = [
    "ModelSpec",
    "MODEL_REGISTRY",
    "DownloadError",
    "download_model",
    "ensure_models",
    "select_models",
]

