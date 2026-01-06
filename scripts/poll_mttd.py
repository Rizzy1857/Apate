#!/usr/bin/env python3
"""
MTTD Polling Script
-------------------
Periodically fetches /mttd endpoint and logs to CSV for baseline collection.

Usage:
  python scripts/poll_mttd.py --url http://localhost:8000 --interval 300 --output mttd_baseline.csv

The script will run in the background, polling every N seconds, and append results to the CSV.
Timestamps are in UTC. Run for 2+ weeks to collect sufficient baseline data.
"""

import argparse
import csv
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_mttd(url: str) -> dict | None:
    """Fetch /mttd endpoint and return parsed JSON, or None on error."""
    mttd_url = f"{url}/mttd" if url.endswith("/") else f"{url}/mttd"
    try:
        with urllib.request.urlopen(mttd_url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.URLError as e:
        logger.error(f"Failed to fetch {mttd_url}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {mttd_url}: {e}")
        return None
    except Exception as e:  # pragma: no cover
        logger.error(f"Unexpected error fetching {mttd_url}: {e}")
        return None


def flatten_mttd_for_csv(data: dict, timestamp: str) -> dict:
    """Flatten nested /mttd response into flat dict for CSV row."""
    row = {"timestamp": timestamp}

    # Top-level fields
    row["active_sessions"] = data.get("active_sessions", 0)
    row["total_completed"] = data.get("total_completed", 0)

    # 24h MTTD metrics
    mttd_24h = data.get("mttd_24h", {})
    row["mttd_24h_mean"] = mttd_24h.get("mttd_mean", 0)
    row["mttd_24h_median"] = mttd_24h.get("mttd_median", 0)
    row["mttd_24h_sample_size"] = mttd_24h.get("sample_size", 0)
    row["mttd_24h_discovery_rate"] = mttd_24h.get("discovery_rate", 0)
    row["mttd_24h_total_sessions"] = mttd_24h.get("total_sessions", 0)

    # 7d MTTD metrics
    mttd_7d = data.get("mttd_7d", {})
    row["mttd_7d_mean"] = mttd_7d.get("mttd_mean", 0)
    row["mttd_7d_median"] = mttd_7d.get("mttd_median", 0)
    row["mttd_7d_sample_size"] = mttd_7d.get("sample_size", 0)
    row["mttd_7d_discovery_rate"] = mttd_7d.get("discovery_rate", 0)
    row["mttd_7d_total_sessions"] = mttd_7d.get("total_sessions", 0)

    return row


def main():
    parser = argparse.ArgumentParser(
        description="Poll /mttd endpoint periodically and log to CSV"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of honeypot (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Poll interval in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--output",
        default="mttd_baseline.csv",
        help="Output CSV file (default: mttd_baseline.csv)",
    )

    args = parser.parse_args()

    logger.info(f"Starting MTTD polling: url={args.url}, interval={args.interval}s, output={args.output}")

    csv_file = open(args.output, "a", newline="")
    writer = None

    try:
        poll_count = 0
        while True:
            timestamp = datetime.now(timezone.utc).isoformat()
            data = fetch_mttd(args.url)

            if data:
                row = flatten_mttd_for_csv(data, timestamp)

                # Write header on first row
                if writer is None:
                    writer = csv.DictWriter(csv_file, fieldnames=row.keys())
                    writer.writeheader()
                    csv_file.flush()

                writer.writerow(row)
                csv_file.flush()

                poll_count += 1
                logger.info(
                    f"Poll #{poll_count}: active={row['active_sessions']}, "
                    f"completed={row['total_completed']}, "
                    f"mttd_24h={row['mttd_24h_mean']:.1f}s"
                )
            else:
                logger.warning(f"Poll #{poll_count + 1}: Failed to fetch data, will retry in {args.interval}s")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info(f"Interrupted. Wrote {poll_count} polls to {args.output}")
    finally:
        csv_file.close()


if __name__ == "__main__":
    main()
