"""
Database Connection and Session Management
------------------------------------------
Sets up database connections, session management, and provides utilities
for database operations in the Mirage honeypot system.
"""

import os
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .database import Base
from .config import get_config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and sessions"""
    
    def __init__(self):
        self.config = get_config()
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return
        
        try:
            # Create synchronous engine
            sync_url = self.config.database.url
            self.engine = create_engine(
                sync_url,
                pool_pre_ping=True,
                echo=self.config.logging.level == "DEBUG"
            )
            
            # Create async engine
            async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")
            self.async_engine = create_async_engine(
                async_url,
                pool_pre_ping=True,
                echo=self.config.logging.level == "DEBUG"
            )
            
            # Create session factories
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            self.AsyncSessionLocal = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self._initialized = True
            logger.info("Database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def create_tables(self):
        """Create all database tables"""
        if not self._initialized:
            await self.initialize()
        
        try:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    async def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        if not self._initialized:
            await self.initialize()
        
        try:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise
    
    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        if not self._initialized:
            try:
                await self.initialize()
            except:
                return False
        
        try:
            async with self.AsyncSessionLocal() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def get_sync_session(self) -> Session:
        """Get a synchronous database session"""
        if not self._initialized:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()
    
    async def get_async_session(self) -> AsyncSession:
        """Get an asynchronous database session"""
        if not self._initialized:
            await self.initialize()
        return self.AsyncSessionLocal()
    
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Async context manager for database sessions with automatic cleanup"""
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def cleanup(self):
        """Clean up database connections"""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()
        self._initialized = False
        logger.info("Database connections cleaned up")

# Global database manager instance
db_manager = DatabaseManager()

# Dependency injection for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database sessions"""
    async with db_manager.session_scope() as session:
        yield session

# Utility functions for common database operations
async def get_or_create_attacker_profile(source_ip: str, session: AsyncSession):
    """Get existing attacker profile or create a new one"""
    from .database import AttackerProfileDB
    from sqlalchemy import select
    
    # Try to get existing profile
    result = await session.execute(
        select(AttackerProfileDB).where(AttackerProfileDB.source_ip == source_ip)
    )
    profile = result.scalar_one_or_none()
    
    if profile is None:
        # Create new profile
        profile = AttackerProfileDB(
            source_ip=source_ip,
            session_count=0,
            total_interactions=0,
            common_commands=[],
            common_user_agents=[],
            attack_patterns=[],
            risk_score=0.0,
            tags=[]
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    
    return profile

async def update_attacker_profile(source_ip: str, session_data: dict, session: AsyncSession):
    """Update attacker profile with new session data"""
    from .database import AttackerProfileDB
    from sqlalchemy import select, update
    from datetime import datetime
    
    # Get existing profile
    result = await session.execute(
        select(AttackerProfileDB).where(AttackerProfileDB.source_ip == source_ip)
    )
    profile = result.scalar_one_or_none()
    
    if profile:
        # Update profile statistics
        updates = {
            'last_seen': datetime.utcnow(),
            'session_count': profile.session_count + 1,
            'total_interactions': profile.total_interactions + session_data.get('interaction_count', 0)
        }
        
        # Update common commands if provided
        if 'commands' in session_data:
            existing_commands = profile.common_commands or []
            new_commands = session_data['commands']
            # Merge and keep most common (simple approach)
            all_commands = existing_commands + new_commands
            command_counts = {}
            for cmd in all_commands:
                command_counts[cmd] = command_counts.get(cmd, 0) + 1
            # Keep top 20 most common commands
            top_commands = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            updates['common_commands'] = [cmd for cmd, _ in top_commands]
        
        # Update user agents if provided
        if 'user_agent' in session_data and session_data['user_agent']:
            existing_agents = profile.common_user_agents or []
            if session_data['user_agent'] not in existing_agents:
                existing_agents.append(session_data['user_agent'])
                updates['common_user_agents'] = existing_agents[-10:]  # Keep last 10
        
        # Apply updates
        await session.execute(
            update(AttackerProfileDB)
            .where(AttackerProfileDB.source_ip == source_ip)
            .values(**updates)
        )
        await session.commit()

async def store_honeytoken_trigger(token_id: str, source_ip: str, session: AsyncSession):
    """Record that a honeytoken was triggered"""
    from .database import HoneytokenDB
    from sqlalchemy import select, update
    from datetime import datetime
    
    # Get honeytoken
    result = await session.execute(
        select(HoneytokenDB).where(HoneytokenDB.token_id == token_id)
    )
    honeytoken = result.scalar_one_or_none()
    
    if honeytoken:
        # Update trigger statistics
        triggered_ips = honeytoken.triggered_by_ips or []
        if source_ip not in triggered_ips:
            triggered_ips.append(source_ip)
        
        updates = {
            'times_triggered': honeytoken.times_triggered + 1,
            'last_triggered_at': datetime.utcnow(),
            'triggered_by_ips': triggered_ips
        }
        
        if honeytoken.first_triggered_at is None:
            updates['first_triggered_at'] = datetime.utcnow()
        
        await session.execute(
            update(HoneytokenDB)
            .where(HoneytokenDB.token_id == token_id)
            .values(**updates)
        )
        await session.commit()

# Database initialization for application startup
async def init_database():
    """Initialize database on application startup"""
    try:
        await db_manager.initialize()
        
        # Check if we can connect
        if not await db_manager.check_connection():
            logger.warning("Database connection check failed")
            return False
        
        # Create tables if they don't exist
        await db_manager.create_tables()
        
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

# Database cleanup for application shutdown
async def cleanup_database():
    """Clean up database connections on application shutdown"""
    await db_manager.cleanup()
    logger.info("Database cleanup completed")
