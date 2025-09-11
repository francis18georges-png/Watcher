"""Train a simple linear regression model on the sample dataset.

The dataset is expected at ``datasets/simple_linear.csv`` with columns
``x`` and ``y``.  The script fits ``y = w * x + b`` using gradient descent
and prints the learned parameters and mean squared error.
"""

from __future__ import annotations

import csv
from pathlib import Path

DATA_PATH = Path("datasets/simple_linear.csv")


def load_data() -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    with DATA_PATH.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            x, y = map(float, row)
            xs.append(x)
            ys.append(y)
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
    xs, ys = load_data()
    w, b, mse = train(xs, ys)
    print(f"w={w:.3f}, b={b:.3f}, mse={mse:.4f}")


if __name__ == "__main__":
    main()
