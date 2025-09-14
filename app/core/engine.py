"""Core orchestration engine for the Watcher project."""

from pathlib import Path
import json
import time
from itertools import chain
from threading import Thread

from config import load_config

from app.core import autograder as AG
from app.core.benchmark import Bench
from app.core.evaluator import QualityGate
from app.core.memory import Memory
from app.core.planner import Planner
from app.core.learner import Learner
from app.llm.client import Client
from app.core.validation import validate_prompt
from app.core.critic import Critic
from app.core.reasoning import ReasoningChain
from app.tools.scaffold import create_python_cli
from app.data import pipeline
from app.data.validation import validate_feedback_schema
from app.tools import plugins
from app.utils.metrics import metrics
from app.core.logging_setup import get_logger


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
        self.critic = Critic()
        self.plugins: list[plugins.Plugin] = []
        self._load_plugins()
        self.start_msg = self._bootstrap()
        self.last_prompt = ""
        self.last_answer = ""
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

    def chat(self, prompt: str, reasoning: ReasoningChain | None = None) -> str:
        """Generate a response to *prompt* using the LLM client.

        Parameters
        ----------
        prompt:
            User provided input.
        reasoning:
            Optional :class:`ReasoningChain` instance used to record explicit
            reasoning steps.  When supplied, the prompt and resulting answer are
            appended to the chain and stored in memory for later inspection.
        """
        start_time = time.perf_counter()
        try:
            user_prompt = validate_prompt(prompt)
            # Store the user prompt and the assistant answer using distinct
            # memory kinds so analytics can differentiate between them.
            self.mem.add("chat_user", user_prompt)
            if reasoning is not None:
                reasoning.add(f"prompt: {user_prompt}")

            # Use the critic to obtain structured suggestions for the prompt.  If
            # the prompt lacks essential qualities we reply with these suggestions
            # rather than querying the LLM which keeps the tests lightweight and
            # mirrors the behaviour of a real assistant that would ask the user to
            # clarify their question first.
            suggestions = self.critic.suggest(user_prompt)
            if suggestions:
                # Map suggestion identifiers to short human messages.
                mapping = {
                    "detail": "Voici quelques détails supplémentaires.",
                    "politeness": "manque de politesse",
                }
                msg = ", ".join(mapping.get(s, s) for s in suggestions)
                self.mem.add("chat_ai", msg)
                self.last_prompt = user_prompt
                self.last_answer = msg
                if reasoning is not None:
                    reasoning.add(f"answer: {msg}")
                    reasoning.save(self.mem)
                metrics.log_response_time(time.perf_counter() - start_time)
                if hasattr(self, "bench"):
                    metrics.log_evaluation_score(self.bench.run_variant("chat"))
                return msg

            # Retrieve texts most similar to the prompt from memory.  Extract
            # regular excerpts and detail suggestions separately so the latter can
            # be surfaced in the final response without polluting the prompt sent
            # to the LLM.
            results = self.mem.search(user_prompt)
            excerpts = [t for _s, _i, k, t in results if k != "detail"]
            details = [t for _s, _i, k, t in results if k == "detail"]

            # Combine the original prompt with retrieved excerpts before sending to
            # the LLM.
            llm_prompt = user_prompt
            if excerpts:
                llm_prompt = "\n\n".join([llm_prompt, "\n".join(excerpts)])

            answer, trace = self.client.generate(llm_prompt)

            if details:
                answer += "\n\nVoici quelques détails supplémentaires.\n" + "\n".join(
                    details
                )

            self.mem.add("chat_ai", answer)
            self.mem.add("trace", trace)
            if reasoning is not None:
                reasoning.add(f"answer: {answer}")
                reasoning.save(self.mem)
            self.last_prompt = user_prompt
            self.last_answer = answer
            metrics.log_response_time(time.perf_counter() - start_time)
            if hasattr(self, "bench"):
                metrics.log_evaluation_score(self.bench.run_variant("chat"))
            return answer
        except Exception as exc:
            metrics.log_error(str(exc))
            raise

    def add_feedback(self, rating: float, kind: str = "chat") -> str:
        """Persist user feedback on the last exchange.

        Parameters
        ----------
        rating:
            Score assigned by the user between ``0.0`` and ``1.0``.
        kind:
            Feedback category, defaults to ``"chat"``.

        Returns
        -------
        str
            Confirmation message or ``"no response to rate"`` when nothing was
            rated.

        Raises
        ------
        ValueError
            If ``rating`` is outside the ``0.0``–``1.0`` interval.
        """
        if not 0.0 <= rating <= 1.0:
            raise ValueError("rating must be between 0.0 and 1.0")
        if not self.last_prompt or not self.last_answer:
            return "no response to rate"
        self.mem.add_feedback(kind, self.last_prompt, self.last_answer, rating)
        return "feedback enregistré"

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
        qg_res: str | None = None
        try:
            qg_res = self.run_quality_gate()
        except Exception:  # pragma: no cover - best effort
            logger.exception("run_quality_gate failed")
        try:
            self.auto_improve(qg_res)
        except Exception:  # pragma: no cover - best effort
            logger.exception("auto_improve failed")

    def run_quality_gate(self) -> str:
        """Run static checks and tests, storing the result in memory."""
        res = self.qg.run_all()
        self.mem.add("quality", json.dumps(res))
        return json.dumps(res)

    def prepare_data(self) -> str:
        """Execute the data preparation pipeline."""
        try:
            start = time.perf_counter()
            raw = pipeline.load_raw_data()
            validate_feedback_schema(raw)
            cleaned = pipeline.clean_data(raw)
            path = pipeline.transform_data(cleaned)
            logger.info(
                "data prepared in %.3fs -> %s", time.perf_counter() - start, path
            )
        except Exception:  # pragma: no cover - best effort
            logger.exception("data preparation failed")
            return "data preparation failed"
        return str(path)

    def auto_improve(
        self,
        qg_res: str | None = None,
        state: list[float] | None = None,
        reward: float | None = None,
    ) -> str:
        """Train on datasets, update policy and perform a simple A/B benchmark.

        If *qg_res* is ``None`` the quality gate is executed to obtain a fresh
        result.  When a recent result is already available it can be passed in
        to avoid running the expensive checks twice.
        """
        if qg_res is None:
            # Only execute the quality gate if a recent result wasn't
            # supplied.  ``run_quality_gate`` already persists the result
            # in memory so there is no need to keep the return value here.
            self.run_quality_gate()
        fb_iter = self.mem.iter_feedback()
        try:
            first = next(fb_iter)
        except StopIteration:
            first = None
        if first is not None:
            raw_dir = self.base / "datasets" / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_file = raw_dir / "data.json"
            data = [
                {
                    "kind": k,
                    "prompt": p,
                    "answer": a,
                    "rating": r,
                }
                for k, p, a, r in chain([first], fb_iter)
            ]
            raw_file.write_text(
                json.dumps({"feedback": data}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        self.prepare_data()
        rep = AG.grade_all()
        self.mem.add("train", json.dumps(rep))

        if state is not None and reward is not None:
            self.learner.step(state, reward)

        comp = self.learner.compare("A", "B")
        self.mem.add("decision", json.dumps(comp))
        a = comp["A"]
        b = comp["B"]
        keep = comp["best"]["name"]
        return f"train_ok={rep.get('ok', False)} A={a:.3f} B={b:.3f} keep={keep}"

    # ------------------------------------------------------------------
    # Plugin related helpers

    def _load_plugins(self) -> None:
        """Populate :attr:`plugins` from ``plugins.toml``."""

        self.plugins = plugins.reload_plugins(self.base)

    def reload_plugins(self) -> str:
        """Reload plugins without restarting the engine."""

        self._load_plugins()
        return f"{len(self.plugins)} plugins rechargés"

    def run_plugins(self) -> list[str]:
        """Execute all loaded plugins and return their outputs."""
        return [p.run() for p in self.plugins]
logger = get_logger(__name__)
