"""Train a simple linear regression model on the sample dataset.

The dataset is expected at ``datasets/simple_linear.csv`` with columns
``x`` and ``y``.  The script fits ``y = w * x + b`` using gradient descent
and prints the learned parameters and mean squared error.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from app.core import logging_setup

DATA_PATH = Path("datasets/simple_linear.csv")


def load_data() -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    with DATA_PATH.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # skip header
            for line_no, row in enumerate(reader, start=2):
                try:
                    x, y = map(float, row)
                except ValueError as exc:
                    raise ValueError(f"Invalid data at line {line_no}: {row}") from exc
                xs.append(x)
                ys.append(y)
        except (ValueError, StopIteration) as exc:
            raise ValueError("Malformed or incomplete CSV data") from exc

    if not xs or not ys:
        raise ValueError("Dataset contains no data")

    return xs, ys


def train(
    xs: list[float], ys: list[float], lr: float = 0.01, epochs: int = 1000
) -> tuple[float, float, float]:
    w = 0.0
    b = 0.0
    n = len(xs)
    for _ in range(epochs):
        y_pred = [w * x + b for x in xs]
        dw = (-2 / n) * sum((y - yp) * x for x, y, yp in zip(xs, ys, y_pred))
        db = (-2 / n) * sum((y - yp) for y, yp in zip(ys, y_pred))
        w -= lr * dw
        b -= lr * db
    mse = sum((y - (w * x + b)) ** 2 for x, y in zip(xs, ys)) / n
    return w, b, mse


def main() -> None:
    logging_setup.configure()
    logger = logging.getLogger(__name__)
    xs, ys = load_data()
    w, b, mse = train(xs, ys)
    logger.info("w=%0.3f, b=%0.3f, mse=%0.4f", w, b, mse)


if __name__ == "__main__":
    main()
