import json
import logging
import os
import shutil
import subprocess
import tkinter as tk
from http.server import BaseHTTPRequestHandler, HTTPServer
from tkinter import messagebox, ttk
from threading import Thread

from app.core import logging_setup
from app.core.engine import Engine
from app.utils.metrics import PerformanceMetrics, metrics


logger = logging.getLogger(__name__)


APP_NAME = "Watcher"
_SCORE_ERROR = "La note doit être comprise entre 0.0 et 1.0."


def _validate_score(raw_score: float) -> float:
    """Ensure *raw_score* falls within the accepted 0.0–1.0 interval."""

    if not 0.0 <= raw_score <= 1.0:
        raise ValueError(_SCORE_ERROR)
    return raw_score


class MetricsHandler(BaseHTTPRequestHandler):
    metrics: PerformanceMetrics = metrics

    def do_GET(self) -> None:  # pragma: no cover - simple server
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        payload = {
            "engine_calls": self.metrics.engine_calls,
            "db_calls": self.metrics.db_calls,
            "plugin_calls": self.metrics.plugin_calls,
            "engine_time_total": self.metrics.engine_time_total,
            "db_time_total": self.metrics.db_time_total,
            "plugin_time_total": self.metrics.plugin_time_total,
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_metrics_server(
    port: int = 8000, metrics_obj: PerformanceMetrics | None = None
) -> HTTPServer:
    """Start a background HTTP server exposing metrics."""

    MetricsHandler.metrics = metrics_obj or metrics
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


class WatcherApp(ttk.Frame):
    _PLUGIN_REFRESH_MS = 2000

    def __init__(self, master: tk.Tk, *, offline: bool = False):
        super().__init__(master)
        self.engine = Engine()
        master.title(APP_NAME)
        master.geometry("1100x700")
        master.minsize(900, 600)
        self.pack(fill="both", expand=True)
        self._plugin_rows: dict[str, str] = {}
        self._plugin_refresh_job: str | None = None
        self._build()
        if offline:
            self.engine.set_offline_mode(True)
        self._update_status_label()
        self.out.insert("end", f"[Watcher] {self.engine.start_msg}\n")
        self.out.see("end")
        self.bind("<Destroy>", self._on_destroy)
        self._refresh_plugin_metrics()

    def _build(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.chat = ttk.Frame(nb)
        self.brief = ttk.Frame(nb)
        self.atelier = ttk.Frame(nb)
        self.bench = ttk.Frame(nb)
        self.docs = ttk.Frame(nb)
        self.plugins_panel = ttk.Frame(nb)
        for t, frm in [
            ("Chat", self.chat),
            ("Briefing", self.brief),
            ("Atelier", self.atelier),
            ("Bench", self.bench),
            ("Docs", self.docs),
            ("Plugins", self.plugins_panel),
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
        self.send_btn = ttk.Button(bottom, text="Envoyer", command=self._send)
        self.send_btn.pack(side="left", padx=8)
        ttk.Label(bottom, text="Note (0.0 – 1.0)").pack(side="left")
        self.rate_var = tk.DoubleVar(value=0.0)
        self.rate_input = tk.Spinbox(
            bottom,
            from_=0.0,
            to=1.0,
            increment=0.1,
            textvariable=self.rate_var,
            width=4,
        )
        self.rate_input.pack(side="left", padx=4)
        ttk.Button(bottom, text="Noter", command=self._rate).pack(side="left")
        status_bar = ttk.Frame(self)
        status_bar.pack(fill="x", padx=8, pady=(0, 8))
        self.status_var = tk.StringVar(value="")
        self.status = ttk.Label(status_bar, textvariable=self.status_var)
        self.status.pack(side="left", fill="x", expand=True)
        self.offline_btn = ttk.Button(status_bar, text="Mode offline: désactivé", command=self._toggle_offline)
        self.offline_btn.pack(side="right")

        plugins_frame = ttk.Frame(self.plugins_panel)
        plugins_frame.pack(fill="both", expand=True, padx=8, pady=8)
        columns = ("plugin", "cpu", "memory")
        self.plugin_tree = ttk.Treeview(
            plugins_frame,
            columns=columns,
            show="headings",
            height=8,
        )
        headings = {
            "plugin": "Plugin",
            "cpu": "CPU (%)",
            "memory": "RAM (MiB)",
        }
        for col, title in headings.items():
            self.plugin_tree.heading(col, text=title)
            anchor = "w" if col == "plugin" else "center"
            self.plugin_tree.column(col, anchor=anchor, width=120 if col != "plugin" else 200)
        self.plugin_tree.pack(fill="both", expand=True)

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
        self.out.insert("end", f"\n[You] {q}\n")
        self.out.see("end")
        self.inp.delete("1.0", "end")
        self.send_btn.state(["disabled"])

        def done(ans: str) -> None:
            self.out.insert("end", f"[Watcher] {ans}\n")
            self.out.see("end")
            self.send_btn.state(["!disabled"])

        self._run_in_thread(lambda: self.engine.chat(q), done)

    def _brief(self) -> None:
        spec = self.engine.run_briefing()
        self.out.insert("end", f"\n[Brief] {spec}\n")
        self.out.see("end")

    def _scaffold(self) -> None:
        msg = self.engine.scaffold_from_brief()
        self.out.insert("end", f"\n[Scaffold] {msg}\n")
        self.out.see("end")

    def _run_in_thread(self, fn, done=None) -> None:
        def task() -> None:
            try:
                rep = fn()
            except Exception as e:  # pragma: no cover - threading
                logger.exception("Unhandled exception in worker thread")
                rep = str(e)
            cb = done or (lambda r: messagebox.showerror(APP_NAME, r))
            self.after(0, lambda: cb(rep))

        Thread(target=task, daemon=True).start()

    def _run_async(self, fn, tag: str) -> None:
        pb = ttk.Progressbar(self.atelier, mode="indeterminate")
        pb.pack(fill="x", padx=8, pady=4)
        pb.start()

        self._run_in_thread(fn, lambda rep: self._task_done(pb, tag, rep))

    def _task_done(self, pb: ttk.Progressbar, tag: str, rep: str) -> None:
        pb.stop()
        pb.destroy()
        self.out.insert("end", f"\n[{tag}] {rep}\n")
        self.out.see("end")

    def _tests(self) -> None:
        self._run_async(self.engine.run_quality_gate, "Tests")

    def _improve(self) -> None:
        self._run_async(self.engine.auto_improve, "Improve")

    def _rate(self) -> None:
        try:
            raw_value = float(self.rate_var.get())
        except (tk.TclError, TypeError, ValueError):
            messagebox.showerror(APP_NAME, _SCORE_ERROR)
            return

        try:
            score = _validate_score(raw_value)
        except ValueError:
            messagebox.showerror(APP_NAME, _SCORE_ERROR)
            return

        msg = self.engine.add_feedback(score)
        self.out.insert("end", f"\n[Feedback] {msg}\n")
        self.out.see("end")

    def _update_status_label(self) -> None:
        mode = "Hors ligne" if self.engine.offline_mode else "Sur"
        backend = getattr(self.engine.client, "host", "ollama")
        model = getattr(self.engine.client, "model", "llama3.2:3b")
        self.status_var.set(f"Mode: {mode} | Backend: {backend} | Modèle: {model}")
        state = "activé" if self.engine.offline_mode else "désactivé"
        self.offline_btn.config(text=f"Mode offline: {state}")

    def _toggle_offline(self) -> None:
        new_state = not self.engine.offline_mode
        msg = self.engine.set_offline_mode(new_state)
        self._update_status_label()
        self.out.insert("end", f"\n[Mode] {msg}\n")
        self.out.see("end")

    def _refresh_plugin_metrics(self) -> None:
        data = self.engine.plugin_metrics()
        known = set(self._plugin_rows)
        for entry in data:
            name = entry["name"]
            cpu = entry["cpu"]
            mem = entry["memory"]
            cpu_txt = "—" if cpu is None else f"{cpu:.1f} %"
            mem_txt = "—" if mem is None else f"{mem:.1f} MiB"
            item_id = self._plugin_rows.get(name)
            values = (name, cpu_txt, mem_txt)
            if item_id is None:
                item_id = self.plugin_tree.insert("", "end", values=values)
                self._plugin_rows[name] = item_id
            else:
                self.plugin_tree.item(item_id, values=values)
            known.discard(name)

        for stale in known:
            item_id = self._plugin_rows.pop(stale, None)
            if item_id is not None:
                self.plugin_tree.delete(item_id)

        self._plugin_refresh_job = self.after(self._PLUGIN_REFRESH_MS, self._refresh_plugin_metrics)

    def _on_destroy(self, event: tk.Event) -> None:  # pragma: no cover - Tk cleanup
        if event.widget is self and self._plugin_refresh_job is not None:
            self.after_cancel(self._plugin_refresh_job)
            self._plugin_refresh_job = None


def run_app(*, offline: bool = False, status_only: bool = False) -> int:
    """Run the graphical or CLI version of Watcher."""

    logging_setup.configure()
    if status_only:
        mode = "hors ligne" if offline else "en ligne"
        print(
            "Watcher prêt (mode "
            f"{mode}). Lancez `python -m app.ui.main` pour l'interface graphique "
            "et utilisez le bouton Mode offline pour couper l'LLM."
        )
        return 0

    start_metrics_server()

    if not os.environ.get("DISPLAY"):
        if shutil.which("Xvfb"):
            logger.warning("DISPLAY absent, lancement de Xvfb...")
            xvfb = subprocess.Popen(["Xvfb", ":99"])
            os.environ["DISPLAY"] = ":99"
            try:
                root = tk.Tk()
                WatcherApp(root, offline=offline)
                root.mainloop()
            finally:
                xvfb.terminate()
        else:
            logger.warning("DISPLAY absent et Xvfb introuvable, mode CLI activé.")
            eng = Engine()
            if offline:
                eng.set_offline_mode(True)
            logger.info("%s", eng.start_msg)
            try:
                while True:
                    q = input("[You] ").strip()
                    if q.lower() in {"exit", "quit"}:
                        break
                    if q.lower().startswith("rate "):
                        try:
                            score = float(q.split()[1])
                            score = _validate_score(score)
                        except (IndexError, ValueError):
                            logger.warning(_SCORE_ERROR)
                            continue
                        logger.info("%s", eng.add_feedback(score))
                        continue
                    if not q:
                        continue
                    ans = eng.chat(q)
                    logger.info("%s", ans)
            except (EOFError, KeyboardInterrupt):
                pass
    else:
        root = tk.Tk()
        try:
            WatcherApp(root, offline=offline)
            root.mainloop()
        except Exception as e:  # pragma: no cover - UI
            messagebox.showerror("Watcher", str(e))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_app())
