"""Validate the checksum of a prepared dataset."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from common import get_nested, load_params


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="Dataset to validate")
    parser.add_argument(
        "--params",
        type=Path,
        default=Path("params.yaml"),
        help="Parameter file containing validation expectations",
    )
    parser.add_argument(
        "--dataset-key",
        default="simple_linear",
        help="Key under the 'validate' section describing the dataset",
    )
    return parser.parse_args()


def compute_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    if not args.file.exists():
        raise FileNotFoundError(f"Dataset not found: {args.file}")

    params = load_params(args.params)
    dataset_cfg = get_nested(params, ["validate", args.dataset_key])
    expected_hash = str(dataset_cfg.get("expected_hash"))
    if not expected_hash:
        raise KeyError(
            f"Missing 'expected_hash' for dataset {args.dataset_key} in {args.params}"
        )

    actual_hash = compute_md5(args.file)
    if actual_hash != expected_hash:
        raise ValueError(
            f"Hash mismatch for {args.file}. Expected {expected_hash} but found {actual_hash}."
        )


if __name__ == "__main__":
    main()
