# Metrics and measurement

Reviewed 2026-09-25. Metrics support diagnosis and experiments; they do not replace raw evidence reconciliation. Definitions and acceptance targets are in [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md).

The core calls `start_metrics_server()` and defaults to port 8000, configurable by `CHRONOS_METRICS_PORT`. Failure to bind is logged but does not stop core startup, so verify reachability and scrape health explicitly.

The optional `monitoring` Compose profile runs `dashboard-exporter` on port 9100 plus Prometheus and Grafana. Exporter variables are `CHRONOS_DASHBOARD_METRICS_PORT`, `CHRONOS_PG_*`, and `CHRONOS_REDIS_*`. The current exporter has development credential defaults; supply credentials and use least-privilege roles for controlled deployments.

Current caveats:

- `chronos_dashboard_active_sessions` means distinct sessions with audit activity in the last ten minutes, not lifecycle-active sessions.
- Average session duration hides distribution and censoring; do not use it as deception quality or MTTD.
- Provenance gauges scan active session blob metadata and do not establish lifetime generation totals.
- Collector counters/histograms are process-local and reset on restart unless the monitoring design accounts for it.
- Scrape success, exporter health, queue lag, pending spool records and summary watermark are different health signals.

Run the optional profile only after inspecting merged Compose configuration:

```bash
docker compose --profile monitoring up -d dashboard-exporter prometheus grafana
```

Do not expose development metrics or Grafana publicly. Record scrape configuration and instrumentation version with research runs.
