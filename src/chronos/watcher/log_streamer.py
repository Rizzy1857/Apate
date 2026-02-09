"""
Audit Log Streamer
Monitors PostgreSQL audit logs and streams events in real-time
"""
import logging
import time
import threading
import json
from datetime import datetime
from typing import Callable, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuditLogStreamer:
    """
    Streams audit logs from PostgreSQL to subscribers
    Implements pub-sub pattern for real-time event processing
    """
    
    def __init__(self, db_config: Dict[str, str], poll_interval: float = 1.0):
        """
        Args:
            db_config: PostgreSQL connection parameters
            poll_interval: How often to poll for new events (seconds)
        """
        self.db_config = db_config
        self.poll_interval = poll_interval
        self.subscribers: List[Callable] = []
        self.running = False
        self.thread = None
        self.last_id = 0
        
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to audit log events"""
        self.subscribers.append(callback)
        logger.info(f"[Watcher] New subscriber registered: {callback.__name__}")
        
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from events"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"[Watcher] Subscriber removed: {callback.__name__}")
            
    def _get_connection(self):
        """Create PostgreSQL connection"""
        # Type ignore needed for psycopg2 dict unpacking
        return psycopg2.connect(**self.db_config)  # type: ignore
        
    def _fetch_new_events(self, conn) -> List[Dict[str, Any]]:
        """Fetch events newer than last_id"""
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    id, timestamp, inode, operation, path, 
                    pid, uid, metadata, session_id
                FROM audit_log
                WHERE id > %s
                ORDER BY id ASC
                LIMIT 1000
            """, (self.last_id,))
            
            events = cursor.fetchall()
            if events:
                self.last_id = events[-1]['id']
            return events
            
    def _notify_subscribers(self, event: Dict[str, Any]):
        """Notify all subscribers of new event"""
        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception as e:
                logger.error(f"[Watcher] Subscriber {subscriber.__name__} error: {e}")
                
    def _poll_loop(self):
        """Main polling loop"""
        logger.info("[Watcher] Starting audit log polling...")
        
        while self.running:
            try:
                conn = self._get_connection()
                events = self._fetch_new_events(conn)
                conn.close()
                
                for event in events:
                    # Convert datetime to string for JSON serialization
                    if 'timestamp' in event and event['timestamp']:
                        event['timestamp'] = event['timestamp'].isoformat()
                    
                    # Parse metadata JSON if exists
                    if 'metadata' in event and isinstance(event['metadata'], str):
                        try:
                            event['metadata'] = json.loads(event['metadata'])
                        except:
                            pass
                    
                    self._notify_subscribers(dict(event))
                    
                if events:
                    logger.debug(f"[Watcher] Processed {len(events)} new events")
                    
            except Exception as e:
                logger.error(f"[Watcher] Poll error: {e}")
                
            time.sleep(self.poll_interval)
            
    def start(self):
        """Start the log streamer"""
        if self.running:
            logger.warning("[Watcher] Already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info("[Watcher] Audit log streamer started")
        
    def stop(self):
        """Stop the log streamer"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("[Watcher] Audit log streamer stopped")
        
    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events from the database"""
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        id, timestamp, inode, operation, path,
                        pid, uid, metadata, session_id
                    FROM audit_log
                    ORDER BY id DESC
                    LIMIT %s
                """, (limit,))
                
                events = cursor.fetchall()
                conn.close()
                
                # Convert to dict and format
                result = []
                for event in events:
                    event_dict = dict(event)
                    if event_dict.get('timestamp'):
                        event_dict['timestamp'] = event_dict['timestamp'].isoformat()
                    result.append(event_dict)
                    
                return result
        except Exception as e:
            logger.error(f"[Watcher] Error fetching recent events: {e}")
            return []
            
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about audit logs"""
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Total events
                cursor.execute("SELECT COUNT(*) as total FROM audit_log")
                total = cursor.fetchone()['total']
                
                # Events by operation
                cursor.execute("""
                    SELECT operation, COUNT(*) as count
                    FROM audit_log
                    GROUP BY operation
                    ORDER BY count DESC
                """)
                by_operation = {row['operation']: row['count'] for row in cursor.fetchall()}
                
                # Recent activity (last hour)
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM audit_log
                    WHERE timestamp > NOW() - INTERVAL '1 hour'
                """)
                last_hour = cursor.fetchone()['count']
                
                # Unique sessions
                cursor.execute("SELECT COUNT(DISTINCT session_id) as count FROM audit_log")
                sessions = cursor.fetchone()['count']
                
                conn.close()
                
                return {
                    "total_events": total,
                    "by_operation": by_operation,
                    "last_hour": last_hour,
                    "unique_sessions": sessions,
                    "last_processed_id": self.last_id
                }
        except Exception as e:
            logger.error(f"[Watcher] Error fetching stats: {e}")
            return {}


# Example usage and testing
if __name__ == "__main__":
    # Example configuration
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "chronos",
        "user": "chronos",
        "password": "chronos_secret"
    }
    
    streamer = AuditLogStreamer(db_config, poll_interval=2.0)
    
    # Example subscriber
    def print_event(event):
        print(f"[EVENT] {event['operation']} at {event['path']} (inode: {event['inode']})")
    
    streamer.subscribe(print_event)
    streamer.start()
    
    try:
        while True:
            time.sleep(10)
            stats = streamer.get_stats()
            print(f"\n[STATS] Total: {stats.get('total_events', 0)}, Last Hour: {stats.get('last_hour', 0)}")
    except KeyboardInterrupt:
        print("\nStopping...")
        streamer.stop()
