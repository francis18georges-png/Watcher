import json
import time
import urllib.request

import pytest

from app.utils.metrics import PerformanceMetrics
from app.ui.main import start_metrics_server


def test_metrics_logging() -> None:
    pm = PerformanceMetrics()
    pm.log_response_time(0.5)
    pm.log_evaluation_score(0.8)
    pm.log_error("oops")
    assert pm.response_times == [0.5]
    assert pm.evaluation_scores == [0.8]
    assert pm.error_logs == ["oops"]


def test_component_counters_increment() -> None:
    pm = PerformanceMetrics()

    with pm.track_engine():
        time.sleep(0.01)
    with pm.track_db():
        time.sleep(0.01)
    with pm.track_plugin():
        time.sleep(0.01)

    assert pm.engine_calls == 1
    assert pm.db_calls == 1
    assert pm.plugin_calls == 1
    assert len(pm.engine_response_times) == 1
    assert len(pm.db_response_times) == 1
    assert len(pm.plugin_response_times) == 1
    assert pm.engine_time_total == pytest.approx(sum(pm.engine_response_times))
    assert pm.db_time_total == pytest.approx(sum(pm.db_response_times))
    assert pm.plugin_time_total == pytest.approx(sum(pm.plugin_response_times))


def test_metrics_endpoint() -> None:
    pm = PerformanceMetrics()
    server = start_metrics_server(port=0, metrics_obj=pm)
    port = server.server_address[1]
    with pm.track_engine():
        time.sleep(0.01)
    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics")
    data = json.loads(resp.read())
    server.shutdown()
    server.server_close()
    assert data["engine_calls"] == 1
    assert "engine_time_total" in data


def test_max_entries_limit() -> None:
    pm = PerformanceMetrics(max_entries=2)
    for i in range(4):
        pm.log_response_time(float(i))
        pm.log_evaluation_score(float(i))
        pm.log_error(str(i))
    assert pm.response_times == [2.0, 3.0]
    assert pm.evaluation_scores == [2.0, 3.0]
    assert pm.error_logs == ["2", "3"]

    pm2 = PerformanceMetrics(max_entries=2)
    for _ in range(4):
        with pm2.track_engine():
            pass
        with pm2.track_db():
            pass
        with pm2.track_plugin():
            pass
    assert len(pm2.engine_response_times) == 2
    assert len(pm2.db_response_times) == 2
    assert len(pm2.plugin_response_times) == 2
    assert len(pm2.response_times) == 2
    assert pm2.engine_calls == 4
    assert pm2.db_calls == 4
    assert pm2.plugin_calls == 4
