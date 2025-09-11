from app.utils.metrics import PerformanceMetrics


def test_metrics_logging() -> None:
    pm = PerformanceMetrics()
    pm.log_response_time(0.5)
    pm.log_evaluation_score(0.8)
    pm.log_error("oops")
    assert pm.response_times == [0.5]
    assert pm.evaluation_scores == [0.8]
    assert pm.error_logs == ["oops"]

