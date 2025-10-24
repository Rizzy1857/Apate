"""
Pytest configuration
--------------------
Ensures the repository root is on sys.path so tests can import 'backend.app.*'.
"""

import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
