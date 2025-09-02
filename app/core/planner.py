# Planner: clarification obligatoire
class Planner:
    def briefing(self) -> str:
        template = [
            "objectif: ...",
            "entrees: ...",
            "sorties: ...",
            "plateforme: windows",
            "contraintes: ...",
            "licence: MIT",
            "livrables: ...",
            "critere_succes: ...",
        ]
        return "\n".join(template)
