"""
Compatibility Entrypoint
------------------------
This module delegates to the canonical FastAPI app at backend/app/main.py.
It exists to preserve older run commands like `python backend/main.py`.
"""

from app.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)