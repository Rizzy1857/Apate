# Chronos Framework

> **Cognitive Deception Infrastructure**  
> *From Theoretical Specification to Deployable Asset*

Chronos is a high-fidelity honeypot framework designed to solve the "state hallucination" problem in cyber deception. Unlike traditional honeypots that emulate services via scripts, Chronos implements a fully consistent **FUSE Filesystem** backed by a **Redis State Hypervisor**, allowing it to behave exactly like a real Linux system while intercepting and analyzing every attacker interaction.

## 🚀 Key Features

*   **State Consistency**: A "State Hypervisor" ensures filesystem operations are atomic and persistent. If an attacker creates a file, it stays there. No more disappearing artifacts.
*   **FUSE Interface**: Intercepts system calls at the kernel-user boundary. Supports standard tools (`ls`, `cat`, `rm`, `vi`, `gcc`) without modification.
*   **Cognitive Intelligence**: Integrated **Persona Engine** generates content for files on-the-fly using LLMs (OpenAI/Anthropic) only when accessed, creating an infinite, realistic depth.
*   **Layer 0 Routing**: High-performance Rust-based traffic analysis (adapted from Project Mirage) for initial threat tagging.
*   **Audit Logging**: Every filesystem operation requires a commit to the PostgreSQL audit log for forensic replay.

## 🏗️ Architecture

Chronos is built on three pillars:

1.  **The Foundation (Data & State)**: 
    *   **Hot State**: Redis 7.0 for milliseconds-latency filesystem metadata (inodes, directory maps).
    *   **Cold Storage**: PostgreSQL 15 for audit logs and forensic data.
2.  **The Interface (FUSE)**:
    *   Python-based FUSE implementation interfacing with the Linux kernel.
    *   Translates VFS calls (`getattr`, `read`, `write`) into Redis atomic transactions.
3.  **The Intelligence (LLM)**:
    *   **Persona Engine**: Injects personality (e.g., "Vulnerable Database Server") into generated content.
    *   **Lazy Generation**: Config files (`/etc/passwd`, `/etc/nginx.conf`) are generated continuously upon first read.

## ⚡ Quick Start

### Prerequisites
*   Docker & Docker Compose
*   (Optional) OpenAI/Anthropic API Key for intelligence features

### Run the Stack

1.  **Clone & Build**:
    ```bash
    git clone https://github.com/Rizzy1857/Apate.git chronos
    cd chronos
    docker compose up --build -d
    ```

2.  **Verify Status**:
    ```bash
    docker compose logs -f core-engine
    ```

3.  **Interact (Simulate Attack)**:
    Enter the container to experience the FUSE filesystem:
    ```bash
    docker exec -it chronos_core /bin/bash
    cd /mnt/honeypot
    
    # Try standard commands
    ls -la
    touch malware.sh
    echo "rm -rf /" > malware.sh
    cat malware.sh
    ```

## 🛠️ Configuration

Environment variables in `docker-compose.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Hostname of Redis service | `redis-store` |
| `POSTGRES_HOST` | Hostname of Postgres service | `db-store` |
| `LLM_PROVIDER` | `openai`, `anthropic`, or `mock` | `mock` |
| `OPENAI_API_KEY` | Key for OpenAI (if used) | - |

## 📚 Documentation

*   [System Architecture](docs/ARCHITECTURE.md)
*   [Developer Guide](docs/DEVELOPMENT.md) (Coming Soon)

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
