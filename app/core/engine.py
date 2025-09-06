"""Core orchestration engine for the Watcher project."""

from pathlib import Path
import json
import logging
from threading import Thread

from config import load_config

from app.core import autograder as AG
from app.core.benchmark import Bench
from app.core.evaluator import QualityGate
from app.core.memory import Memory
from app.core.planner import Planner
from app.core.learner import Learner
from app.llm.client import Client
from app.tools.scaffold import create_python_cli
from app.data import pipeline


class Engine:
    """High level interface coordinating memory, planning and benchmarking."""

    def __init__(self, perform_maintenance: bool = False) -> None:
        self.base = Path(__file__).resolve().parents[2]

        cfg = load_config().get("memory", {})

        db_path = cfg.get("db_path", "memory/mem.db")
        path = Path(db_path)
        if not path.is_absolute():
            path = self.base / path

        self.mem = Memory(path)
        self.qg = QualityGate()
        self.bench = Bench()
        self.learner = Learner(self.bench, self.base / "data")
        self.planner = Planner()
        self.client = Client()
        self.start_msg = self._bootstrap()
        if perform_maintenance:
            Thread(target=self.perform_maintenance, daemon=True).start()

    def _bootstrap(self) -> str:
        """Load context and set up an initial ready agent."""
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

        return ctx

    def chat(self, prompt: str) -> str:
        """Generate a response to *prompt* using the LLM client."""
        # Store the user prompt and the assistant answer using distinct
        # memory kinds so analytics can differentiate between them.
        self.mem.add("chat_user", prompt)
        answer = self.client.generate(prompt)
        self.mem.add("chat_ai", answer)
        return answer

    def run_briefing(self, objective: str = "Projet démo") -> str:
        """Generate a project brief and persist it to the data directory."""
        spec = self.planner.briefing(objective)
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

    def perform_maintenance(self) -> None:
        """Run quality gate and auto-improvement routines."""
        try:
            self.run_quality_gate()
        except Exception:  # pragma: no cover - best effort
            logging.exception("run_quality_gate failed")
        try:
            self.auto_improve()
        except Exception:  # pragma: no cover - best effort
            logging.exception("auto_improve failed")

    def run_quality_gate(self) -> str:
        """Run static checks and tests, storing the result in memory."""
        res = self.qg.run_all()
        self.mem.add("quality", json.dumps(res))
        return json.dumps(res)

    def prepare_data(self) -> str:
        """Execute the data preparation pipeline."""
        try:
            raw = pipeline.load_raw_data()
            cleaned = pipeline.clean_data(raw)
            path = pipeline.transform_data(cleaned)
        except Exception:  # pragma: no cover - best effort
            logging.exception("data preparation failed")
            return "data preparation failed"
        return str(path)

    def auto_improve(self) -> str:
        """Train on datasets and perform a simple A/B benchmark."""
        self.prepare_data()
        rep = AG.grade_all()
        self.mem.add("train", json.dumps(rep))
        comp = self.learner.compare("A", "B")
        self.mem.add("decision", json.dumps(comp))
        a = comp["A"]
        b = comp["B"]
        keep = comp["best"]["name"]
        return f"train_ok={rep.get('ok', False)} A={a:.3f} B={b:.3f} keep={keep}"
