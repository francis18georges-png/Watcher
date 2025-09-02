"""Core orchestration engine for the Watcher project."""

from pathlib import Path
import json
import sys

from app.core import autograder as AG
from app.core.benchmark import Bench
from app.core.collector import DataCollector
from app.core.evaluator import QualityGate
from app.core.memory import Memory
from app.core.planner import Planner
from app.tools.scaffold import create_python_cli


class Engine:
    """High level interface coordinating memory, planning and benchmarking."""

    def __init__(self) -> None:
        self.base = Path(__file__).resolve().parents[2]
        self.mem = Memory(self.base / "memory" / "mem.db")
        self.qg = QualityGate()
        self.bench = Bench()
        self.planner = Planner()
        self.collector = DataCollector(self.base / "datasets")
        self.allow_auto = False
        self.start_msg = self._bootstrap()

    def _bootstrap(self) -> str:
        """Load context and run automatic routines for a ready agent."""
        data_dir = self.base / "data"
        data_dir.mkdir(exist_ok=True, parents=True)

        # Initial conversation context
        ctx_file = data_dir / "initial_context.txt"
        if ctx_file.exists():
            ctx = ctx_file.read_text(encoding="utf-8")
        else:
            ctx = "Watcher prêt. Utilisez l'onglet Chat pour dialoguer."
            ctx_file.write_text(ctx, encoding="utf-8")
        self.mem.add("context", ctx)

        # Ensure a briefing is available
        brief_file = data_dir / "brief.yaml"
        if brief_file.exists():
            self.mem.add("brief", brief_file.read_text(encoding="utf-8"))
        else:
            self.run_briefing()

        # Preload a system prompt for conversations
        prompt_file = data_dir / "conversation_prompt.txt"
        if prompt_file.exists():
            prompt = prompt_file.read_text(encoding="utf-8")
        else:
            prompt = (
                "Tu es Watcher, un assistant de développement Python. "
                "Réponds de manière concise et utile."
            )
            prompt_file.write_text(prompt, encoding="utf-8")
        self.mem.add("system_prompt", prompt)

        # Automatic maintenance, gated behind a one-time permission
        self.allow_auto = self._ask_permission()
        if self.allow_auto:
            try:
                self.run_quality_gate()
            except Exception:  # pragma: no cover - best effort
                pass
            try:
                self.auto_improve()
            except Exception:  # pragma: no cover - best effort
                pass
            try:
                self.collector.prepare()
            except Exception:  # pragma: no cover - best effort
                pass

        return ctx

    def chat(self, prompt: str) -> str:
        """Record a chat message and return a placeholder response."""
        self.mem.add("chat", prompt)
        return "ping"

    def collect_examples(self, urls: list[str]) -> str:
        """Collect new training examples from the given URLs.

        The operation requires prior user consent. Scraping is logged and
        the log path is stored in memory.
        """

        if not self.allow_auto:
            return "permission_required"
        log = self.collector.scrape(urls)
        self.mem.add("collect", log.read_text(encoding="utf-8"))
        return str(log)

    def learn_from_feedback(self, feedback: str) -> str:
        """Replay training datasets while storing human feedback."""

        self.mem.add("feedback", feedback)
        return self.auto_improve()

    def _ask_permission(self) -> bool:
        """Prompt the user once per session for running automatic routines."""
        if not sys.stdin.isatty():
            return True
        ans = (
            input(
                "Autoriser l'exécution des vérifications et de l'apprentissage ? [y/N] "
            )
            .strip()
            .lower()
        )
        return ans.startswith("y")

    def run_briefing(self) -> str:
        """Generate a project brief and persist it to the data directory."""
        spec = self.planner.briefing()
        (self.base / "data").mkdir(exist_ok=True, parents=True)
        (self.base / "data" / "brief.yaml").write_text(spec, encoding="utf-8")
        self.mem.add("brief", spec)
        return "brief.yaml généré"

    def scaffold_from_brief(self) -> str:
        """Create a Python CLI scaffold from the previously generated brief."""
        name = "demo_cli"
        proj = create_python_cli(name, self.base)
        self.mem.add("scaffold", proj)
        return f"scaffold: {proj}"

    def run_quality_gate(self) -> str:
        """Run static checks and tests, storing the result in memory."""
        res = self.qg.run_all()
        self.mem.add("quality", json.dumps(res))
        return json.dumps(res)

    def auto_improve(self) -> str:
        """Train on datasets and perform a simple A/B benchmark."""
        rep = AG.grade_all()
        self.mem.add("train", json.dumps(rep))
        a = self.bench.run_variant("A")
        b = self.bench.run_variant("B")
        keep = "A" if a >= b else "B"
        self.mem.add("decision", json.dumps({"A": a, "B": b, "keep": keep}))
        return f"train_ok={rep.get('ok', False)} A={a:.3f} B={b:.3f} keep={keep}"
