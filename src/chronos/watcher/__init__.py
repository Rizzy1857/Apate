"""
Watcher Module - Real-time audit log monitoring and streaming
"""
from .log_streamer import AuditLogStreamer
from .event_processor import EventProcessor

__all__ = ['AuditLogStreamer', 'EventProcessor']
