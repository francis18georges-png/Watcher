import importlib
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import tkinter as tk
from collections.abc import Iterable, Mapping
from typing import Any
from http.server import BaseHTTPRequestHandler, HTTPServer
from tkinter import messagebox, ttk
from threading import Thread

from app.core import logging_setup
from app.core.engine import Engine
from app.utils.metrics import PerformanceMetrics, metrics
from config import get_settings


if importlib.util.find_spec("psutil") is not None:  # pragma: no cover - optional dependency
    psutil = importlib.import_module("psutil")  # type: ignore[import-not-found]
else:  # pragma: no cover - fallback to lightweight stub
    from app.utils import psutil_stub as psutil  # type: ignore[assignment]


_PSUTIL_EXCEPTIONS: tuple[type[BaseException], ...] = tuple(
    exc
    for exc in (
        getattr(psutil, "Error", None),
        getattr(psutil, "NoSuchProcess", None),
        getattr(psutil, "AccessDenied", None),
        getattr(psutil, "ZombieProcess", None),
    )
    if isinstance(exc, type) and issubclass(exc, BaseException)
)
_COMMON_PROCESS_ERRORS: tuple[type[BaseException], ...] = (ProcessLookupError, PermissionError)
_PSUTIL_EXCEPTIONS = _PSUTIL_EXCEPTIONS + tuple(
    exc for exc in _COMMON_PROCESS_ERRORS if exc not in _PSUTIL_EXCEPTIONS
)
if not _PSUTIL_EXCEPTIONS:
    _PSUTIL_EXCEPTIONS = _COMMON_PROCESS_ERRORS or (Exception,)


logger = logging.getLogger(__name__)


APP_NAME = "Watcher"
_SCORE_ERROR = "La note doit être comprise entre 0.0 et 1.0."


def _validate_score(raw_score: float) -> float:
    """Ensure *raw_score* falls within the accepted 0.0–1.0 interval."""

    if not 0.0 <= raw_score <= 1.0:
        raise ValueError(_SCORE_ERROR)
    return raw_score


def _get_entry_attr(entry: object, name: str) -> Any:
    """Return attribute *name* from *entry* supporting mapping access."""

    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


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
        self._plugin_process_cache: dict[str, psutil.Process] = {}
        self._sandbox_processes: list[dict[str, Any]] = []
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
        self.status = ttk.Label(
            self,
            text=(
                f"Mode: {self.settings.ui.mode} | "
                f"Backend: {self.settings.llm.backend} | "
                f"Modèle: {self.settings.llm.model}"
            ),
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

        monitor = ttk.LabelFrame(self.atelier, text="Plugins en cours")
        monitor.pack(fill="both", expand=True, padx=8, pady=(12, 8))

        columns = ("pid", "plugin", "cpu", "rss", "threads")
        self.plugin_tree = ttk.Treeview(
            monitor,
            columns=columns,
            show="headings",
            height=6,
        )
        headings = {
            "pid": "PID",
            "plugin": "Plugin",
            "cpu": "CPU %",
            "rss": "RSS",
            "threads": "Threads",
        }
        widths = {"pid": 80, "plugin": 260, "cpu": 80, "rss": 120, "threads": 80}
        for column in columns:
            self.plugin_tree.heading(column, text=headings[column])
            self.plugin_tree.column(column, width=widths[column], anchor="center")
        self.plugin_tree.pack(fill="both", expand=True, padx=8, pady=8)

        after = getattr(self, "after", None)
        if callable(after):
            after(1000, self._update_plugin_monitor)

    def _collect_plugin_stats(
        self, entries: Iterable[object] | None = None
    ) -> list[dict[str, Any]]:
        """Return runtime statistics about active plugin sandbox processes."""

        if entries is None:
            entries = getattr(self, "_sandbox_processes", [])

        if not hasattr(self, "_plugin_process_cache"):
            self._plugin_process_cache = {}

        cache: dict[str, psutil.Process] = self._plugin_process_cache
        stats: list[dict[str, Any]] = []
        active_keys: set[str] = set()

        for entry in entries:
            pid = _get_entry_attr(entry, "pid")
            if pid is None:
                continue

            try:
                pid_int = int(pid)
            except (TypeError, ValueError):
                continue

            plugin_obj = _get_entry_attr(entry, "plugin")
            import_path = None
            if plugin_obj is not None:
                import_path = _get_entry_attr(plugin_obj, "import_path")
            if not import_path:
                import_path = _get_entry_attr(entry, "import_path")
            if not import_path:
                import_path = str(pid_int)

            key = f"{pid_int}:{import_path}"
            active_keys.add(key)

            process = cache.get(key)
            if process is None or getattr(process, "pid", pid_int) != pid_int:
                try:
                    process = psutil.Process(pid_int)
                except _PSUTIL_EXCEPTIONS:
                    cache.pop(key, None)
                    continue

                cache[key] = process
                try:
                    process.cpu_percent(None)
                except _PSUTIL_EXCEPTIONS:
                    cache.pop(key, None)
                    continue
                cpu_percent = 0.0
            else:
                try:
                    cpu_percent = float(process.cpu_percent(None))
                except _PSUTIL_EXCEPTIONS:
                    cache.pop(key, None)
                    continue

            try:
                mem_info = process.memory_info()
            except AttributeError:
                rss = vms = 0
            except _PSUTIL_EXCEPTIONS:
                cache.pop(key, None)
                continue
            else:
                rss = getattr(mem_info, "rss", 0)
                vms = getattr(mem_info, "vms", 0)

            try:
                num_threads = int(process.num_threads())
            except AttributeError:
                num_threads = 0
            except _PSUTIL_EXCEPTIONS:
                cache.pop(key, None)
                continue

            try:
                process_name = process.name()
            except AttributeError:
                process_name = ""
            except _PSUTIL_EXCEPTIONS:
                cache.pop(key, None)
                continue

            plugin_name = None
            if plugin_obj is not None:
                plugin_name = _get_entry_attr(plugin_obj, "name")
            if plugin_name is None:
                plugin_name = _get_entry_attr(entry, "name")

            stats.append(
                {
                    "key": key,
                    "pid": pid_int,
                    "import_path": import_path,
                    "cpu_percent": cpu_percent,
                    "rss": rss,
                    "vms": vms,
                    "num_threads": num_threads,
                    "process_name": process_name,
                    "plugin_name": plugin_name,
                }
            )

        stale_keys = [key for key in cache if key not in active_keys]
        for key in stale_keys:
            cache.pop(key, None)

        self._plugin_stats_snapshot = stats
        return stats

    def _update_plugin_monitor(self) -> None:
        """Refresh the plugin process Treeview with current sandbox data."""

        entries: list[dict[str, Any]] = []
        engine = getattr(self, "engine", None)
        if engine is not None:
            getter = getattr(engine, "get_sandbox_processes", None)
            if callable(getter):
                entries = list(getter())
            else:
                entries = list(getattr(engine, "_sandbox_processes", []))

        self._sandbox_processes = entries
        stats = self._collect_plugin_stats(entries)

        tree = getattr(self, "plugin_tree", None)
        if tree is None:
            return

        try:
            children = list(tree.get_children())
        except Exception:
            children = []
        for item in children:
            try:
                tree.delete(item)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Unable to remove Treeview item %s", item, exc_info=True)

        for stat in stats:
            cpu_percent = float(stat.get("cpu_percent", 0.0) or 0.0)
            values = (
                stat.get("pid"),
                stat.get("plugin_name") or stat.get("import_path"),
                f"{cpu_percent:.1f}",
                stat.get("rss", 0),
                stat.get("num_threads", 0),
            )
            try:
                tree.insert("", "end", values=values, text=stat.get("import_path", ""))
            except Exception:  # pragma: no cover - Treeview failure is non-critical
                logger.debug("Unable to insert plugin monitor row", exc_info=True)

        after = getattr(self, "after", None)
        if callable(after):
            try:
                after(1000, self._update_plugin_monitor)
            except Exception:  # pragma: no cover - scheduling errors are non-fatal
                logger.debug("Unable to reschedule plugin monitor", exc_info=True)

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
