"""Prepare the sample dataset used by the training script."""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from random import Random
from typing import Iterable

from common import get_nested, load_params

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to the raw CSV file")
    parser.add_argument(
        "--output", type=Path, required=True, help="Location where the cleaned CSV will be stored"
    )
    parser.add_argument(
        "--params",
        type=Path,
        default=Path("params.yaml"),
        help="Parameter file containing preparation hyperparameters",
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def deduplicate(rows: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    seen: set[tuple[float, float]] = set()
    unique: list[tuple[float, float]] = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        unique.append(row)
    return unique


def write_rows(path: Path, rows: Iterable[tuple[float, float]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["x", "y"])
        writer.writeheader()
        for x, y in rows:
            if float(x).is_integer():
                x_out: float | int = int(x)
            else:  # pragma: no cover - not expected in current dataset
                x_out = x
            if float(y).is_integer():
                y_out: float | int = int(y)
            else:  # pragma: no cover - not expected in current dataset
                y_out = y
            writer.writerow({"x": x_out, "y": y_out})


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    params = load_params(args.params)
    prepare_cfg = get_nested(params, ["prepare"])

    sample_size = int(prepare_cfg.get("sample_size", 0))
    random_seed = int(prepare_cfg.get("random_seed", 0))

    if not args.input.exists():
        raise FileNotFoundError(f"Raw dataset not found: {args.input}")

    raw_rows: list[tuple[float, float]] = []
    with args.input.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("The raw dataset is missing a header row")
        expected_fields = {"x", "y"}
        missing = expected_fields - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing expected columns: {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            try:
                x_val = float(row["x"])
                y_val = float(row["y"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value at line {line_no}: {row}") from exc
            raw_rows.append((x_val, y_val))

    rng = Random(random_seed)
    if raw_rows:
        rng.shuffle(raw_rows)

    unique_rows = deduplicate(raw_rows)
    sorted_rows = sorted(unique_rows, key=lambda pair: pair[0])
    if sample_size > 0:
        selected_rows = sorted_rows[:sample_size]
    else:
        selected_rows = sorted_rows

    if not selected_rows:
        raise ValueError("No rows available after preprocessing")

    write_rows(args.output, selected_rows)
    logger.info(
        "Prepared %s rows from %s and wrote them to %s", len(selected_rows), args.input, args.output
    )


if __name__ == "__main__":
    main()
