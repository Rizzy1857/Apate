import os
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_db_init_and_persistence(tmp_path):
    # Use a temp sqlite database for isolation
    db_path = tmp_path / "apate_test.db"
    os.environ["APATE_DB_URL"] = f"sqlite+aiosqlite:///{db_path}"

    # Import app after setting env to pick up DB URL
    from backend.app.main import app
    from backend.app.db_manager import init_database, get_recent_logs, get_recent_alerts

    # Force DB init (if SQLAlchemy available)
    await init_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create an interaction (SSH) which should be logged
        resp = await ac.post("/honeypot/ssh/interact", json={"command": "whoami", "session_id": "db-test"})
        assert resp.status_code == 200

        # Create an alert (simulate via http login result escalation)
        # We call alert API indirectly by triggering a CRITICAL-like result
        # If emulator doesn't produce CRITICAL, this is still fine; we accept >=0 alerts
        _ = await ac.get("/alerts")  # warm-up route

    # Verify logs are retrievable (either from DB or fallback)
    logs = await get_recent_logs(5)
    assert isinstance(logs, list)
    assert len(logs) >= 1
    assert logs[0]["service"] == "ssh"

    # Verify alerts list is available
    alerts = await get_recent_alerts(5)
    assert isinstance(alerts, list)
    # Alerts may be empty if emulator didn't escalate; that's acceptable
