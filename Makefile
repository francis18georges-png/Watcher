.RECIPEPREFIX := >
.PHONY: format lint type security test check

format:
> black .

lint:
> ruff check .
> black --check .

type:
> mypy .

security:
> bandit -q -r . -c bandit.yml
> semgrep --quiet --error --config config/semgrep.yml .

test:
> pytest -q

check: lint type security test

