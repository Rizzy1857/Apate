"""
Alert Notifier
--------------
Sends alerts to a webhook (e.g., Slack) when configured via environment variables.
Includes severity threshold and dedup/backoff to avoid noise.

Env:
- ALERT_WEBHOOK_URL: destination URL (optional)
- ALERT_MIN_LEVEL: minimum level to send (LOW, MEDIUM, HIGH, CRITICAL; default HIGH)
- ALERT_WEBHOOK_TYPE: slack | generic (default slack)
- ALERT_DEDUP_SECONDS: suppress identical alerts within this window (default 300)
"""
from __future__ import annotations

import os
import time
import hashlib
import json
import logging
from typing import Any, Dict

import httpx
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Prometheus counters
ALERTS_SENT = Counter(
    "apate_alerts_sent_total",
    "Alerts sent successfully",
    labelnames=("level", "type"),
)
ALERTS_FAILED = Counter(
    "apate_alerts_failed_total",
    "Alert send failures",
    labelnames=("level", "type", "reason"),
)

_LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
_MIN_LEVEL = os.getenv("ALERT_MIN_LEVEL", "HIGH").upper()
_WEBHOOK_TYPE = os.getenv("ALERT_WEBHOOK_TYPE", "slack").lower()
_DEDUP_SECONDS = int(os.getenv("ALERT_DEDUP_SECONDS", "300"))

_last_sent: Dict[str, float] = {}


def _should_send(level: str) -> bool:
    return _LEVEL_ORDER.get(level.upper(), 0) >= _LEVEL_ORDER.get(_MIN_LEVEL, 2)


def _dedup_key(level: str, message: str, meta: Dict[str, Any]) -> str:
    payload = json.dumps({"level": level, "message": message, "meta": meta}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _dedup_ok(key: str) -> bool:
    now = time.time()
    last = _last_sent.get(key, 0)
    if now - last < _DEDUP_SECONDS:
        return False
    _last_sent[key] = now
    return True


async def notify_alert(level: str, message: str, meta: Dict[str, Any] | None = None) -> None:
    if not _WEBHOOK_URL:
        return  # not configured, silently ignore
    if not _should_send(level):
        return

    meta = meta or {}
    key = _dedup_key(level, message, meta)
    if not _dedup_ok(key):
        return

    lvl = level.upper()
    typ = _WEBHOOK_TYPE

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if _WEBHOOK_TYPE == "slack":
                text = f"[{lvl}] {message}"
                payload = {"text": text, "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*{text}*"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"```{json.dumps(meta, indent=2)}```"}},
                ]}
            else:
                payload = {"level": lvl, "message": message, "meta": meta}

            resp = await client.post(_WEBHOOK_URL, json=payload)
            if 200 <= resp.status_code < 300:
                ALERTS_SENT.labels(level=lvl, type=typ).inc()
            else:
                ALERTS_FAILED.labels(level=lvl, type=typ, reason=str(resp.status_code)).inc()
    except Exception as e:  # pragma: no cover
        ALERTS_FAILED.labels(level=lvl, type=typ, reason=e.__class__.__name__).inc()
        logger.warning(f"Alert notify failed: {e}")
