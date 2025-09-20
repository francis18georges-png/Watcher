"""Validate the schema of a prepared dataset."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

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


def validate_columns(actual: Sequence[str], expected: Sequence[str]) -> None:
    if list(actual) != list(expected):
        raise ValueError(
            "Column mismatch. Expected "
            f"{list(expected)} but found {list(actual)}"
        )


def main() -> None:
    args = parse_args()
    if not args.file.exists():
        raise FileNotFoundError(f"Dataset not found: {args.file}")

    params = load_params(args.params)
    dataset_cfg = get_nested(params, ["validate", args.dataset_key])
    expected_columns = dataset_cfg.get("columns")
    if expected_columns is None:
        raise KeyError(
            f"Missing 'columns' for dataset {args.dataset_key} in {args.params}"
        )
    min_rows = int(dataset_cfg.get("min_rows", 1))

    with args.file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Dataset is missing a header row")
        validate_columns(reader.fieldnames, expected_columns)
        row_count = sum(1 for _ in reader)

    if row_count < min_rows:
        raise ValueError(
            f"Dataset {args.file} contains {row_count} rows which is less than the required {min_rows}."
        )


if __name__ == "__main__":
    main()
