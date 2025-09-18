.RECIPEPREFIX := >
.PHONY: format lint type security test check nox

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

