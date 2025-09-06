class Bench:
    def run_variant(self, name: str) -> float:
        # Stub bench: renvoie un score pseudo aléatoire stable par nom
        import hashlib

        h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
        return (h % 1000) / 1000.0
