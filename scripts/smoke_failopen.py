#!/usr/bin/env python3
"""
Smoke test to validate fail-open behavior and basic uptime before MTTD collection.
- Pings root/status
- Exercises SSH and HTTP honeypot endpoints
- Fails fast if non-200 responses occur

Usage:
  python scripts/smoke_failopen.py --base http://localhost:8000
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


def _request(method: str, url: str, payload: dict | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310 - controlled URL
        body = resp.read()
        return resp.status, body.decode("utf-8")


def check_root(base: str):
    status, body = _request("GET", f"{base}/")
    return status == 200, status, body


def check_status(base: str):
    status, body = _request("GET", f"{base}/status")
    return status == 200, status, body


def check_ssh(base: str):
    payload = {"command": "ls -la", "session_id": "smoke"}
    status, body = _request("POST", f"{base}/honeypot/ssh/interact", payload)
    return status == 200, status, body


def check_http(base: str):
    payload = {"username": "admin", "password": "admin123", "ip": "1.2.3.4"}
    status, body = _request("POST", f"{base}/honeypot/http/login", payload)
    return status == 200, status, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000", help="Base URL of the honeypot")
    args = parser.parse_args()

    checks = [
        ("root", check_root),
        ("status", check_status),
        ("ssh", check_ssh),
        ("http", check_http),
    ]

    failures = []
    for name, fn in checks:
        try:
            ok, status, body = fn(args.base)
            if not ok:
                failures.append(f"{name} failed: status {status}, body={body[:200]}")
            else:
                print(f"[{name}] OK status={status} body_preview={body[:120].replace('\n', ' ')}")
        except urllib.error.HTTPError as e:
            failures.append(f"{name} HTTPError: {e.code} {e.reason}")
        except Exception as e:  # pragma: no cover - smoke safety
            failures.append(f"{name} error: {e}")

    if failures:
        print("SMOKE FAILURES:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    else:
        print("SMOKE SUCCESS: all endpoints responded OK")


if __name__ == "__main__":
    main()
