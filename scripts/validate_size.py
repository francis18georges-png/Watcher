"""Validate the size of a prepared dataset."""

from __future__ import annotations

import argparse
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


def main() -> None:
    args = parse_args()
    if not args.file.exists():
        raise FileNotFoundError(f"Dataset not found: {args.file}")

    params = load_params(args.params)
    dataset_cfg = get_nested(params, ["validate", args.dataset_key])
    expected_size_raw = dataset_cfg.get("expected_size")
    if expected_size_raw is None:
        raise KeyError(
            f"Missing 'expected_size' for dataset {args.dataset_key} in {args.params}"
        )

    expected_size = int(expected_size_raw)
    actual_size = args.file.stat().st_size
    if actual_size != expected_size:
        raise ValueError(
            f"Size mismatch for {args.file}. Expected {expected_size} bytes but found {actual_size}."
        )


if __name__ == "__main__":
    main()
