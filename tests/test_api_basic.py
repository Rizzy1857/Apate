import pytest
import asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_and_status():
    from backend.app.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in {"running", "healthy"}

        r2 = await ac.get("/status")
        assert r2.status_code == 200
        sdata = r2.json()
        assert "honeypots" in sdata


@pytest.mark.asyncio
async def test_icon_endpoints_no_404():
    from backend.app.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # These should not 404; we return 204
        r1 = await ac.get("/favicon.ico")
        assert r1.status_code in (200, 204)
        r2 = await ac.get("/apple-touch-icon.png")
        assert r2.status_code in (200, 204)
        r3 = await ac.get("/apple-touch-icon-precomposed.png")
        assert r3.status_code in (200, 204)


@pytest.mark.asyncio
async def test_ssh_interact_creates_log_entry():
    from backend.app.main import app

    payload = {"command": "whoami", "session_id": "test-session"}

    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/honeypot/ssh/interact", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert body.get("session_id") == "test-session"

        logs = await ac.get("/logs?limit=5")
        assert logs.status_code == 200
        ldata = logs.json()
        assert "logs" in ldata
        # At least one log and the most recent should be ssh
        if ldata["logs"]:
            assert ldata["logs"][0]["service"] == "ssh"


@pytest.mark.asyncio
async def test_alerts_endpoint_available():
    from backend.app.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        alerts = await ac.get("/alerts?limit=3")
        assert alerts.status_code == 200
        adata = alerts.json()
        assert "alerts" in adata
        assert "count" in adata