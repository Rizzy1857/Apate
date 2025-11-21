# Apate Honeypot - Dependencies Installation Guide

## Recommended Python Version

- Use Python 3.11 or 3.12 for a smooth setup (matches CI)
- Python 3.13 may require compiling pydantic-core with Rust
  - Either switch to Python 3.11/3.12
  - Or install Rust and then reinstall dependencies

Quick options:

- macOS: `brew install python@3.11` or `brew install rust`

- Linux (Rust): `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

## Python Dependencies

Create and activate a virtual environment, then install requirements:

```bash
# Prefer Python 3.11
python3.11 -m venv venv || python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install FastAPI and dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

If using Python 3.13:
```bash
# Install Rust toolchain first (required for pydantic-core build)
# macOS
# Apate Honeypot - Dependencies Installation Guide

## Recommended Python Version

- Use Python 3.11 or 3.12 for a smooth setup (matches CI)
- Python 3.13 may require compiling pydantic-core with Rust
  - Either switch to Python 3.11/3.12
  - Or install Rust and then reinstall dependencies

Quick options:

- macOS: `brew install python@3.11` or `brew install rust`

- Linux (Rust): `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

## Python Dependencies

Create and activate a virtual environment, then install requirements:

```bash
# Prefer Python 3.11
python3.11 -m venv venv || python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install FastAPI and dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

If using Python 3.13:
```bash
# Install Rust toolchain first (required for pydantic-core build)
# macOS
brew install rust
# Linux (generic)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

## Running Local CI Checks

To ensure your environment is set up correctly and code meets quality standards, run the cross-platform CI script:

```bash
python scripts/ci_check.py
```