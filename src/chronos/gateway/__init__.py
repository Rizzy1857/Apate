"""
Gateway Module - Entry point for attacker traffic
"""
from .ssh_server import SSHHoneypot
from .http_server import HTTPHoneypot

__all__ = ['SSHHoneypot', 'HTTPHoneypot']
