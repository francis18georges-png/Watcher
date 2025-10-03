.RECIPEPREFIX := >
SEED ?= 42
WATCHER_TRAINING__SEED ?= $(SEED)
PYTHONHASHSEED ?= $(WATCHER_TRAINING__SEED)
CUBLAS_WORKSPACE_CONFIG ?= :4096:8
TORCH_DETERMINISTIC ?= 1

export PYTHONHASHSEED
export WATCHER_TRAINING__SEED
export CUBLAS_WORKSPACE_CONFIG
export TORCH_DETERMINISTIC

.PHONY: format lint type security test check nox demo-offline

format:
> ruff --fix .
> ruff format .
> black .

lint:
> nox -s lint

type:
> nox -s typecheck

security:
> nox -s security

test:
> nox -s tests

check:
> nox -s lint typecheck security tests

nox:
> nox -s lint typecheck security tests build

demo-offline:
> mkdir -p .artifacts/demo-offline
> WATCHER_PATHS__BASE_DIR=$$(pwd)/.artifacts/demo-offline \
> WATCHER_INTELLIGENCE__MODE=offline \
> python -m app.cli run --offline --prompt "Présente Watcher en une phrase."

