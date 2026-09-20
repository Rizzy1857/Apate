import os
import time
import logging
from prometheus_client import start_http_server, Gauge
import psycopg2
import redis

logger = logging.getLogger(__name__)

# Metrics
SESSIONS_TOTAL = Gauge('chronos_dashboard_sessions_total', 'Total sessions (last fetch)')
SESSIONS_ACTIVE = Gauge('chronos_dashboard_active_sessions', 'Active sessions in last 10 minutes')
AVG_SESSION_DURATION = Gauge('chronos_dashboard_avg_session_duration_seconds', 'Average session duration (seconds)')
PROVENANCE_LLM = Gauge('chronos_provenance_llm_blobs_total', 'Number of LLM-generated blobs')
PROVENANCE_FALLBACK = Gauge('chronos_provenance_fallback_blobs_total', 'Number of fallback blobs')
PROVENANCE_TEMPLATE = Gauge('chronos_provenance_template_blobs_total', 'Number of template blobs')


def get_pg_conn():
    # Configurable via env vars or default local dev settings
    host = os.environ.get('CHRONOS_PG_HOST', '127.0.0.1')
    port = int(os.environ.get('CHRONOS_PG_PORT', '5433'))
    user = os.environ.get('CHRONOS_PG_USER', 'chronos')
    password = os.environ.get('CHRONOS_PG_PASSWORD', 'chronos_dev_password')
    dbname = os.environ.get('CHRONOS_PG_DB', 'chronos')
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname,
                            connect_timeout=5, options='-c statement_timeout=5000')
    conn.autocommit = True
    return conn


def get_redis_conn():
    host = os.environ.get('CHRONOS_REDIS_HOST', '127.0.0.1')
    port = int(os.environ.get('CHRONOS_REDIS_PORT', '6379'))
    return redis.Redis(host=host, port=port, db=0, decode_responses=True,
                       socket_timeout=3, socket_connect_timeout=3)


def collect_and_set(pg_conn, rd):
    try:
        with pg_conn.cursor() as cur:
            # Total sessions (last 100)
            cur.execute("SELECT COUNT(*) FROM session_evidence")
            total = cur.fetchone()[0] or 0
            SESSIONS_TOTAL.set(total)

            # Active sessions (last 10 minutes)
            cur.execute("SELECT COUNT(DISTINCT session_id) FROM audit_log WHERE timestamp > NOW() - INTERVAL '10 minutes'")
            active = cur.fetchone()[0] or 0
            SESSIONS_ACTIVE.set(active)

            # Average session duration
            cur.execute("SELECT AVG(duration_seconds) FROM session_evidence WHERE duration_seconds IS NOT NULL")
            avg = cur.fetchone()[0] or 0.0
            AVG_SESSION_DURATION.set(float(avg))
    except Exception as e:
        logger.exception("Postgres metrics collection failed: %s", e)
        pg_conn.close()
        return False

    try:
        # Provenance counts from Redis keys fs:blob_meta:*
        keys = rd.scan_iter('session:*:fs:blob_meta:*', count=100)
        llm = 0
        fallback = 0
        template = 0
        for k in keys:
            meta = rd.hgetall(k)
            gen = meta.get('generation_source', 'llm')
            if gen == 'llm':
                llm += 1
            elif gen == 'fallback':
                fallback += 1
            elif gen == 'template':
                template += 1

        PROVENANCE_LLM.set(llm)
        PROVENANCE_FALLBACK.set(fallback)
        PROVENANCE_TEMPLATE.set(template)
    except Exception as e:
        logger.exception("Redis provenance collection failed: %s", e)
        return False
    return True


def main():
    port = int(os.environ.get('CHRONOS_DASHBOARD_METRICS_PORT', '9100'))
    start_http_server(port)
    logger.info(f"Dashboard metrics exporter listening on :{port}")

    pg = None
    rd = None
    while True:
        if pg is None:
            try:
                pg = get_pg_conn()
            except Exception:
                logger.exception("Failed to connect to Postgres; retrying in 5s")
                pg = None
                time.sleep(5)
                continue

        if rd is None:
            try:
                rd = get_redis_conn()
            except Exception:
                logger.exception("Failed to connect to Redis; retrying in 5s")
                rd = None
                time.sleep(5)
                continue

        if not collect_and_set(pg, rd):
            pg.close()
            rd.close()
            pg = rd = None
        time.sleep(10)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
