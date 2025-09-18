"""
Backend package for Apate/Mirage honeypot.

This file makes the 'backend' directory a Python package so test imports like
`from backend.app.honeypot.ssh_emulator import SSHEmulator` resolve correctly.
"""

# Marks backend as a Python package

__all__: list[str] = []
