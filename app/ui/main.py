import tkinter as tk
from tkinter import messagebox, ttk

from app.core.engine import Engine


APP_NAME = "Watcher"


class WatcherApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.engine = Engine()
        master.title(APP_NAME)
        master.geometry("1100x700")
        master.minsize(900, 600)
        self.pack(fill="both", expand=True)
        self._build()
        self.out.insert("end", f"[Watcher] {self.engine.start_msg}\n")
        self.out.see("end")

    def _build(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.chat = ttk.Frame(nb)
        self.brief = ttk.Frame(nb)
        self.atelier = ttk.Frame(nb)
        self.bench = ttk.Frame(nb)
        self.docs = ttk.Frame(nb)
        for t, frm in [
            ("Chat", self.chat),
            ("Briefing", self.brief),
            ("Atelier", self.atelier),
            ("Bench", self.bench),
            ("Docs", self.docs),
        ]:
            nb.add(frm, text=t)

        # Chat
        top = ttk.Frame(self.chat)
        top.pack(fill="both", expand=True, padx=8, pady=8)
        self.out = tk.Text(top, height=20, wrap="word")
        self.out.pack(fill="both", expand=True)
        bottom = ttk.Frame(self.chat)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        self.inp = tk.Text(bottom, height=4, wrap="word")
        self.inp.pack(side="left", fill="both", expand=True)
        ttk.Button(bottom, text="Envoyer", command=self._send).pack(side="left", padx=8)
        self.status = ttk.Label(
            self,
            text="Mode: Sur | Backend: ollama | Modèle: llama3.2:3b",
        )
        self.status.pack(fill="x")

        # Briefing button
        ttk.Button(self.brief, text="Démarrer le Briefing", command=self._brief).pack(
            padx=12, pady=12, anchor="w"
        )

        # Atelier buttons
        at = ttk.Frame(self.atelier)
        at.pack(fill="x", padx=8, pady=8)
        ttk.Button(at, text="Générer scaffold", command=self._scaffold).pack(
            side="left"
        )
        ttk.Button(at, text="Lancer tests", command=self._tests).pack(
            side="left", padx=6
        )
        ttk.Button(at, text="Améliorer (A/B)", command=self._improve).pack(
            side="left", padx=6
        )

    def _send(self) -> None:
        q = self.inp.get("1.0", "end").strip()
        if not q:
            return
        ans = self.engine.chat(q)
        self.out.insert("end", f"\n[You] {q}\n[Watcher] {ans}\n")
        self.out.see("end")
        self.inp.delete("1.0", "end")

    def _brief(self) -> None:
        spec = self.engine.run_briefing()
        self.out.insert("end", f"\n[Brief] {spec}\n")
        self.out.see("end")

    def _scaffold(self) -> None:
        msg = self.engine.scaffold_from_brief()
        self.out.insert("end", f"\n[Scaffold] {msg}\n")
        self.out.see("end")

    def _tests(self) -> None:
        rep = self.engine.run_quality_gate()
        self.out.insert("end", f"\n[Tests] {rep}\n")
        self.out.see("end")

    def _improve(self) -> None:
        rep = self.engine.auto_improve()
        self.out.insert("end", f"\n[Improve] {rep}\n")
        self.out.see("end")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        WatcherApp(root)
        root.mainloop()
    except Exception as e:  # pragma: no cover - UI
        messagebox.showerror("Watcher", str(e))
