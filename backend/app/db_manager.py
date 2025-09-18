"""
Database Manager (SQLite + Fallback)
------------------------------------
Async SQLAlchemy with SQLite by default. Falls back to in-memory lists if DB
is unavailable. Controlled by APATE_DB_URL env (default: sqlite+aiosqlite:///./apate.db)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, UTC
import asyncio
import logging
import os
import json

# SQLAlchemy (optional at runtime)
try:
    from sqlalchemy.ext.asyncio import (
        create_async_engine,
        async_sessionmaker,
        AsyncSession,
    )
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from sqlalchemy import String, Integer, DateTime, select, Text
    _SA_AVAILABLE = True
except Exception:  # pragma: no cover
    _SA_AVAILABLE = False

logger = logging.getLogger(__name__)

# In-memory fallbacks
_MEM_LOGS: List[Dict[str, Any]] = []
_MEM_ALERTS: List[Dict[str, Any]] = []

# Globals for DB engine/session
_engine = None
_Session: Optional[async_sessionmaker[AsyncSession]] = None
_DB_URL = os.getenv("APATE_DB_URL", "sqlite+aiosqlite:///./apate.db")
# Respect Alembic-managed schema if flag is set
_USE_ALEMBIC = os.getenv("APATE_USE_ALEMBIC", "0") in {"1", "true", "True"}

if _SA_AVAILABLE:
    class Base(DeclarativeBase):
        pass

    class InteractionLog(Base):
        __tablename__ = "interaction_logs"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
        service: Mapped[str] = mapped_column(String(50))
        payload: Mapped[str] = mapped_column(Text)  # JSON serialized

    class Alert(Base):
        __tablename__ = "alerts"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
        level: Mapped[str] = mapped_column(String(20))
        message: Mapped[str] = mapped_column(Text)
        meta: Mapped[str] = mapped_column(Text)  # JSON serialized

# Simulated async DB init/cleanup
async def init_database() -> bool:
    global _engine, _Session
    if not _SA_AVAILABLE:
        logger.info("SQLAlchemy not available; using in-memory fallback.")
        return False
    try:
        _engine = create_async_engine(_DB_URL, pool_pre_ping=True, pool_recycle=180)
        _Session = async_sessionmaker(bind=_engine, expire_on_commit=False)
        async with _engine.begin() as conn:
            if not _USE_ALEMBIC:
                await conn.run_sync(Base.metadata.create_all)
            else:
                logger.info("Skipping create_all; APATE_USE_ALEMBIC is enabled.")
        logger.info(f"DB init complete (url={_DB_URL})")
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning(f"DB init failed: {exc}; using in-memory fallback.")
        _engine = None
        _Session = None
        return False

async def cleanup_database() -> None:
    global _engine
    try:
        if _engine is not None:
            await _engine.dispose()
        logger.info("DB cleanup complete.")
    except Exception:  # pragma: no cover
        pass

# Interaction logging
async def log_interaction(service: str, payload: Dict[str, Any]) -> None:
    if _Session is None:
        _MEM_LOGS.append(
            {"ts": datetime.now(UTC).isoformat(), "service": service, "payload": payload}
        )
        return
    async with _Session() as session:  # type: ignore[misc]
        rec = InteractionLog(
            ts=datetime.now(UTC),
            service=service,
            payload=json.dumps(payload),
        )
        session.add(rec)
        await session.commit()

async def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    if _Session is None:
        return list(reversed(_MEM_LOGS[-limit:]))
    async with _Session() as session:  # type: ignore[misc]
        stmt = select(InteractionLog).order_by(InteractionLog.id.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r.payload)
            except Exception:
                payload = {"raw": r.payload}
            out.append(
                {
                    "ts": r.ts.isoformat(),
                    "service": r.service,
                    "payload": payload,
                }
            )
        return out

# Alerting
async def create_alert(level: str, message: str, meta: Dict[str, Any] | None = None) -> None:
    if _Session is None:
        _MEM_ALERTS.append(
            {"ts": datetime.now(UTC).isoformat(), "level": level, "message": message, "meta": meta or {}}
        )
        return
    async with _Session() as session:  # type: ignore[misc]
        rec = Alert(
            ts=datetime.now(UTC),
            level=level,
            message=message,
            meta=json.dumps(meta or {}),
        )
        session.add(rec)
        await session.commit()

async def get_recent_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    if _Session is None:
        return list(reversed(_MEM_ALERTS[-limit:]))
    async with _Session() as session:  # type: ignore[misc]
        stmt = select(Alert).order_by(Alert.id.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                meta = json.loads(r.meta)
            except Exception:
                meta = {"raw": r.meta}
            out.append(
                {
                    "ts": r.ts.isoformat(),
                    "level": r.level,
                    "message": r.message,
                    "meta": meta,
                }
            )
        return out
