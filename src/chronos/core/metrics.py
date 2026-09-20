import os
import logging

logger = logging.getLogger(__name__)

def start_metrics_server(default_port: int = 8000) -> None:
    """Start Prometheus metrics HTTP server on the configured port.

    Environment variable `CHRONOS_METRICS_PORT` can override the default.
    This wraps `prometheus_client.start_http_server` but degrades gracefully
    if `prometheus_client` is not installed.
    """
    try:
        from prometheus_client import start_http_server
    except Exception:
        logger.warning("prometheus_client not available; metrics endpoint disabled")
        return

    try:
        port_env = os.environ.get("CHRONOS_METRICS_PORT")
        port = int(port_env) if port_env else default_port
    except ValueError:
        port = default_port

    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on :{port}")
    except Exception as e:
        logger.exception("Failed to start Prometheus metrics server: %s", e)
