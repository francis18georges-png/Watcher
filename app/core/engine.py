from pathlib import Path
import json
from app.core.memory import Memory
from app.core.evaluator import QualityGate
from app.core.benchmark import Bench
from app.core.planner import Planner
from app.core import autograder as AG
from app.tools.scaffold import create_python_cli

class Engine:
    def __init__(self):
        self.base = Path(__file__).resolve().parents[2]
        self.mem = Memory(self.base / "memory" / "mem.db")
        self.qg = QualityGate()
        self.bench = Bench()
        self.planner = Planner()

    def chat(self, prompt: str) -> str:
        self.mem.add("chat", prompt)
        return "ping"

    def run_briefing(self) -> str:
        spec = self.planner.briefing()
        (self.base / "data").mkdir(exist_ok=True, parents=True)
        (self.base / "data" / "brief.yaml").write_text(spec, encoding="utf-8")
        self.mem.add("brief", spec)
        return "brief.yaml généré"

    def scaffold_from_brief(self) -> str:
        name = "demo_cli"
        proj = create_python_cli(name, self.base)
        self.mem.add("scaffold", proj)
        return f"scaffold: {proj}"

    def run_quality_gate(self) -> str:
        res = self.qg.run_all()
        self.mem.add("quality", json.dumps(res))
        return json.dumps(res)

    def auto_improve(self) -> str:
        # entraîne sur tous les datasets puis fait un A/B stub
        rep = AG.grade_all()
        self.mem.add("train", json.dumps(rep))
        a = self.bench.run_variant("A")
        b = self.bench.run_variant("B")
        keep = "A" if a >= b else "B"
        self.mem.add("decision", json.dumps({"A":a,"B":b,"keep":keep}))
        return f"train_ok={rep.get('ok',False)} A={a:.3f} B={b:.3f} keep={keep}"
