import importlib
import importlib.util
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
from config import get_settings


_psutil_spec = importlib.util.find_spec("psutil")
if _psutil_spec is not None:
    psutil = importlib.import_module("psutil")
else:
    from app.utils import psutil_stub as psutil


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
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.settings = get_settings()
        self.engine = Engine()
        self.status_var = tk.StringVar(master=master, value="")
        self._plugin_refresh_ms = 2000
        master.title(APP_NAME)
        master.geometry("1100x700")
        master.minsize(900, 600)
        self.pack(fill="both", expand=True)
        self._build()
        self._update_status_label()
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
        self.offline_var = tk.BooleanVar(value=self.engine.is_offline())
        self.offline_toggle = ttk.Checkbutton(
            bottom,
            text="Mode offline",
            variable=self.offline_var,
            command=self._toggle_offline_mode,
        )
        self.offline_toggle.pack(side="left", padx=8)
        stats_frame = ttk.LabelFrame(self.chat, text="Utilisation plugins")
        stats_frame.pack(fill="x", padx=8, pady=(0, 8))
        columns = ("plugin", "cpu", "memory")
        self.plugin_stats = ttk.Treeview(
            stats_frame,
            columns=columns,
            show="headings",
            height=max(len(self.engine.plugins), 1),
        )
        self.plugin_stats.heading("plugin", text="Plugin")
        self.plugin_stats.heading("cpu", text="CPU (%)")
        self.plugin_stats.heading("memory", text="Mémoire (MiB)")
        self.plugin_stats.column("plugin", width=160, anchor="w")
        self.plugin_stats.column("cpu", width=100, anchor="center")
        self.plugin_stats.column("memory", width=140, anchor="center")
        for plugin in self.engine.plugins:
            self.plugin_stats.insert(
                "",
                "end",
                iid=plugin.name,
                values=(plugin.name, "0.0", "0.0"),
            )
        self.plugin_stats.pack(fill="both", expand=True)
        self.status = ttk.Label(self, textvariable=self.status_var)
        self.status.pack(fill="x")
        self.after(self._plugin_refresh_ms, self._refresh_plugin_stats)

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

    def _toggle_offline_mode(self) -> None:
        offline = bool(self.offline_var.get())
        self.engine.set_offline_mode(offline)
        self._update_status_label()

    def _update_status_label(self) -> None:
        offline_state = "activé" if self.engine.is_offline() else "désactivé"
        status_text = (
            f"Mode interface: {self.settings.ui.mode} | "
            f"Offline: {offline_state} | "
            f"Backend: {self.settings.llm.backend} | "
            f"Modèle: {self.settings.llm.model}"
        )
        self.status_var.set(status_text)

    def _collect_plugin_stats(self) -> dict[str, dict[str, float]]:
        plugin_entries = getattr(self.engine, "plugins", [])
        stats: dict[str, dict[str, float]] = {
            plugin.name: {"cpu": 0.0, "memory": 0.0} for plugin in plugin_entries
        }
        if not plugin_entries:
            return stats

        path_to_name = {plugin.import_path: plugin.name for plugin in plugin_entries}

        for proc in psutil.process_iter():
            try:
                cmdline = self._safe_cmdline(proc)
            except Exception:
                continue
            if not cmdline:
                continue

            matched_name: str | None = None
            for import_path, plugin_name in path_to_name.items():
                if any(import_path in part for part in cmdline):
                    matched_name = plugin_name
                    break
            if matched_name is None:
                continue

            stats[matched_name]["cpu"] += self._safe_cpu_percent(proc)
            stats[matched_name]["memory"] += self._safe_memory_mb(proc)

        return stats

    @staticmethod
    def _safe_cmdline(proc) -> list[str]:
        info = getattr(proc, "info", None)
        if isinstance(info, dict):
            cmdline = info.get("cmdline")
            if cmdline:
                return [str(part) for part in cmdline]
        if hasattr(proc, "cmdline"):
            try:
                cmdline = proc.cmdline()
            except Exception:
                return []
            if not cmdline:
                return []
            return [str(part) for part in cmdline]
        return []

    @staticmethod
    def _safe_cpu_percent(proc) -> float:
        try:
            return float(proc.cpu_percent(interval=None))
        except Exception:
            return 0.0

    @staticmethod
    def _safe_memory_mb(proc) -> float:
        try:
            info = proc.memory_info()
        except Exception:
            return 0.0
        rss = getattr(info, "rss", 0.0)
        try:
            rss_value = float(rss)
        except (TypeError, ValueError):
            rss_value = 0.0
        return rss_value / (1024 * 1024)

    def _refresh_plugin_stats(self) -> None:
        tree = getattr(self, "plugin_stats", None)
        if tree is None or not tree.winfo_exists():
            return

        stats = self._collect_plugin_stats()
        expected = set(stats.keys())
        current = set(tree.get_children(""))

        for orphan in current - expected:
            tree.delete(orphan)

        for plugin_name, data in stats.items():
            values = (
                plugin_name,
                f"{data['cpu']:.1f}",
                f"{data['memory']:.1f}",
            )
            if tree.exists(plugin_name):
                tree.item(plugin_name, values=values)
            else:
                tree.insert("", "end", iid=plugin_name, values=values)

        if self._plugin_refresh_ms:
            self.after(self._plugin_refresh_ms, self._refresh_plugin_stats)


if __name__ == "__main__":
    logging_setup.configure()
    start_metrics_server()

    if not os.environ.get("DISPLAY"):
        if shutil.which("Xvfb"):
            logger.warning("DISPLAY absent, lancement de Xvfb...")
            xvfb = subprocess.Popen(["Xvfb", ":99"])
            os.environ["DISPLAY"] = ":99"
            try:
                root = tk.Tk()
                WatcherApp(root)
                root.mainloop()
            finally:
                xvfb.terminate()
        else:
            logger.warning("DISPLAY absent et Xvfb introuvable, mode CLI activé.")
            eng = Engine()
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
            WatcherApp(root)
            root.mainloop()
        except Exception as e:  # pragma: no cover - UI
            messagebox.showerror("Watcher", str(e))
