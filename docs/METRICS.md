# Metrics and Prometheus integration

This project exposes Prometheus metrics from multiple components:

- Chronos core engine: `:8000` (started by `src/chronos/core/main.py` and `main_with_ssh.py`)
- Dashboard metrics exporter (Postgres + Redis derived metrics): `:9100` (script: `src/chronos/core/dashboard_metrics_exporter.py`)

Prometheus configuration (development) is in `config/prometheus/prometheus.yml`. It includes a job `chronos_dashboard_exporter` that scrapes `dashboard-exporter:9100`.

How to run dashboard exporter locally:

```bash
# activate virtualenv
source .venv/bin/activate
# run exporter (defaults to host-local Postgres/Redis)
python3 src/chronos/core/dashboard_metrics_exporter.py
```

Environment variables:

- `CHRONOS_DASHBOARD_METRICS_PORT` — port for exporter (default 9100)
- `CHRONOS_PG_HOST`, `CHRONOS_PG_PORT`, `CHRONOS_PG_USER`, `CHRONOS_PG_PASSWORD`, `CHRONOS_PG_DB` — Postgres connection
- `CHRONOS_REDIS_HOST`, `CHRONOS_REDIS_PORT` — Redis connection

Prometheus scrape config lives at `config/prometheus/prometheus.yml` and should be mounted into your Prometheus container or service in production.
