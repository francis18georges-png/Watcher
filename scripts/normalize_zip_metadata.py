#!/usr/bin/env python3
"""Normalize timestamp metadata in ZIP archives.

This helper rewrites the ZIP entries with deterministic timestamps and updates
the archive comment so reproducible builds can rely on ``SOURCE_DATE_EPOCH``.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import tempfile
import time
import zipfile


def _parse_epoch(value: str) -> int:
    try:
        epoch = int(value)
    except ValueError as exc:  # pragma: no cover - defensive programming
        raise argparse.ArgumentTypeError("epoch must be an integer") from exc
    if epoch < 0:
        raise argparse.ArgumentTypeError("epoch must be positive")
    return epoch


def _normalized_zipinfo(info: zipfile.ZipInfo, date_time: tuple[int, int, int, int, int, int]) -> zipfile.ZipInfo:
    new_info = zipfile.ZipInfo(info.filename)
    new_info.date_time = date_time
    new_info.compress_type = info.compress_type
    new_info.comment = b""
    new_info.extra = info.extra
    new_info.flag_bits = info.flag_bits
    new_info.create_system = info.create_system
    new_info.create_version = info.create_version
    new_info.extract_version = info.extract_version
    new_info.external_attr = info.external_attr
    new_info.internal_attr = info.internal_attr
    new_info.volume = getattr(info, "volume", 0)
    if hasattr(info, "_compresslevel") and info._compresslevel is not None:  # pragma: no cover - CPython specific
        new_info._compresslevel = info._compresslevel
    return new_info


def normalize_zip(archive: pathlib.Path, epoch: int) -> None:
    if not archive.exists():
        raise FileNotFoundError(f"Archive '{archive}' not found")

    normalized_dir = tempfile.mkdtemp(prefix="zip-normalize-")
    normalized_path = pathlib.Path(normalized_dir, archive.name)

    gm_time = time.gmtime(epoch)
    normalized_time = (
        gm_time.tm_year,
        gm_time.tm_mon,
        gm_time.tm_mday,
        gm_time.tm_hour,
        gm_time.tm_min,
        gm_time.tm_sec,
    )

    with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(
        normalized_path,
        "w",
    ) as dest:
        for info in sorted(source.infolist(), key=lambda item: item.filename):
            data = source.read(info.filename)
            new_info = _normalized_zipinfo(info, normalized_time)
            dest.writestr(new_info, data)

        dest.comment = str(epoch).encode("ascii")

    shutil.move(str(normalized_path), archive)
    shutil.rmtree(normalized_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=pathlib.Path, help="Path to the ZIP archive to normalize")
    parser.add_argument(
        "--epoch",
        type=_parse_epoch,
        default=None,
        help="UNIX timestamp to use (defaults to SOURCE_DATE_EPOCH)",
    )
    args = parser.parse_args()

    epoch_env = os.environ.get("SOURCE_DATE_EPOCH")
    epoch = args.epoch if args.epoch is not None else _parse_epoch(epoch_env) if epoch_env else None
    if epoch is None:
        raise SystemExit("SOURCE_DATE_EPOCH is not defined")

    normalize_zip(args.archive, epoch)


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
