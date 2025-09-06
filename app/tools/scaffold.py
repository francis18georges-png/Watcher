from pathlib import Path
import textwrap


def _confirm_overwrite(path: Path) -> bool:
    """Ask the user to confirm overwriting *path*.

    If stdin is not available (e.g. during tests), the function returns
    ``False`` so that the operation is aborted by default.
    """

    try:
        resp = input(f"{path} contient déjà des fichiers. Écraser ? [y/N] ")
    except (
        EOFError,
        OSError,
    ):  # pragma: no cover - non-interactive envs or pytest capture
        return False
    return resp.strip().lower() in {"y", "yes", "o", "oui"}


def create_python_cli(name: str, base: Path):
    proj = base / "app" / "projects" / name
    if proj.exists() and any(proj.iterdir()):
        if not _confirm_overwrite(proj):
            raise FileExistsError(f"Dossier {proj} non vide")

    (proj / name).mkdir(parents=True, exist_ok=True)
    (proj / "tests").mkdir(parents=True, exist_ok=True)

    (proj / f"{name}/__init__.py").write_text("__version__='0.1.0'\n", encoding="utf-8")
    (proj / f"{name}/cli.py").write_text(
        textwrap.dedent(
            f"""\
        import argparse

        def main():
            p = argparse.ArgumentParser(prog="{name}", description="CLI {name}")
            p.add_argument("--ping", action="store_true", help="répond 'pong'")
            args = p.parse_args()
            if args.ping:
                print("pong")

        if __name__ == "__main__":
            main()
    """
        ),
        encoding="utf-8",
    )

    (proj / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""\
        [build-system]
        requires = ["setuptools>=68","wheel"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "{name}"
        version = "0.1.0"
        description = "CLI générée par Watcher"
        requires-python = ">=3.10"
        dependencies = []
        [project.scripts]
        {name} = "{name}.cli:main"
    """
        ),
        encoding="utf-8",
    )

    (proj / "tests/test_cli.py").write_text(
        textwrap.dedent(
            f"""\
        import sys, pathlib, runpy

        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

        def test_ping(capsys):
            argv = sys.argv
            sys.argv = ["{name}", "--ping"]
            try:
                runpy.run_module("{name}.cli", run_name="__main__")
            finally:
                sys.argv = argv
            assert capsys.readouterr().out.strip() == "pong"
    """
        ),
        encoding="utf-8",
    )

    return str(proj)
