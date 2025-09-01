from pathlib import Path
import json, time
from app.core.memory import Memory
from app.core.evaluator import QualityGate
from app.core.benchmark import Bench
from app.core.planner import Planner

class Engine:
    def __init__(self):
        self.base = Path(__file__).resolve().parents[2]
        self.mem = Memory(self.base / 'memory' / 'mem.db')
        self.qg = QualityGate()
        self.bench = Bench()
        self.planner = Planner()

    def chat(self, prompt: str) -> str:
        # Stub: route vers backend LLM ultérieurement
        self.mem.add('chat', prompt)
        return 'ping'

    def run_briefing(self) -> str:
        spec = self.planner.briefing()
        self.mem.add('brief', spec)
        (self.base / 'data' / 'brief.yaml').write_text(spec, encoding='utf-8')
        return 'brief.yaml généré'

    def scaffold_from_brief(self) -> str:
        # TODO: lire brief.yaml, générer scaffold
        return 'scaffold créé (stub)'

    def run_quality_gate(self) -> str:
        res = self.qg.run_all()
        self.mem.add('quality', json.dumps(res))
        return json.dumps(res)

    def auto_improve(self) -> str:
        # A/B + bench, conserve meilleure
        a_score = self.bench.run_variant('A')
        b_score = self.bench.run_variant('B')
        keep = 'A' if a_score >= b_score else 'B'
        self.mem.add('decision', json.dumps({'A':a_score,'B':b_score,'keep':keep}))
        return f'A={a_score:.3f} B={b_score:.3f} → keep {keep}'
