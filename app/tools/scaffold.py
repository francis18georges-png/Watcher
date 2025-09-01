from pathlib import Path
import textwrap

def create_python_cli(name: str, base: Path):
    proj = base / "app" / "projects" / name
    (proj / name).mkdir(parents=True, exist_ok=True)
    (proj / "tests").mkdir(parents=True, exist_ok=True)

    (proj / f"{name}/__init__.py").write_text("__version__='0.1.0'\n", encoding="utf-8")
    (proj / f"{name}/cli.py").write_text(textwrap.dedent(f"""\
        import argparse

        def main():
            p = argparse.ArgumentParser(prog="{name}", description="CLI {name}")
            p.add_argument("--ping", action="store_true", help="répond 'pong'")
            args = p.parse_args()
            if args.ping:
                print("pong")
    """), encoding="utf-8")

    (proj / "pyproject.toml").write_text(textwrap.dedent(f"""\
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
    """), encoding="utf-8")

    (proj / "tests/test_cli.py").write_text(textwrap.dedent(f"""\
        import subprocess, sys, pathlib, importlib.util

        def test_ping():
            root = pathlib.Path(__file__).resolve().parents[1]
            if importlib.util.find_spec("{name}") is None:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", str(root)])
            out = subprocess.check_output(["{name}", "--ping"], text=True).strip()
            assert out == "pong"
    """), encoding="utf-8")

    return str(proj)
