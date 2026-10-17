"""
ubuntu_profile.py
-----------------
Loads the Ubuntu machine profile from config/ubuntu.yaml and provides
access to the canonical MachineState for a session.

There is one supported machine type: Ubuntu. Explicit purpose and user roles
are trusted profile facts. A versioned Redis device record survives session
cleanup; isolated sessions retain immutable snapshots of that record.

State (ubuntu.yaml) is kept strictly separate from behavior (generation_policy.yaml).
"""

import os
import yaml
import json
import time
import hashlib
from typing import Any, Dict, Optional

# Path resolution: config/ is at the project root, two levels above src/chronos/intelligence/
_PROFILE_PATH = os.path.join(
    os.path.dirname(__file__),  # src/chronos/intelligence/
    "..", "..", "..",            # → project root
    "config", "ubuntu.yaml"
)


class UbuntuProfile:
    """
    Loads and exposes the Ubuntu machine profile.

    The profile is loaded once at startup. It is immutable during a run —
    it represents what the machine *is*, not a runtime decision.
    """

    def __init__(self, profile_path: Optional[str] = None):
        path = os.path.abspath(profile_path or _PROFILE_PATH)
        try:
            with open(path, "r") as f:
                self._raw: Dict[str, Any] = yaml.safe_load(f) or {}
        except FileNotFoundError:
            # Fail boringly: log and fall back to a minimal safe default
            print(f"[UbuntuProfile] WARNING: Profile not found at {path}. Using minimal default.")
            self._raw = {
                "ubuntu_version": "24.04",
                "kernel_version": "unknown",
                "hostname": "ubuntu",
                "primary_user": "ubuntu",
                "installed_packages": [],
                "running_services": [],
                "open_ports": [],
                "users": [],
                "groups": [],
                "network_interfaces": [],
                "mounted_drives": [],
                "ssh_config": {},
                "cron_jobs": [],
                "filesystem": {"entries": []},
            }
        except yaml.YAMLError as e:
            raise RuntimeError(f"[UbuntuProfile] Malformed ubuntu.yaml: {e}")

    # ------------------------------------------------------------------
    # Direct accessors (typed for the rest of the codebase)
    # ------------------------------------------------------------------

    @property
    def ubuntu_version(self) -> str:
        return self._raw.get("ubuntu_version", "24.04")

    @property
    def kernel_version(self) -> str:
        return self._raw.get("kernel_version", "unknown")

    @property
    def hostname(self) -> str:
        return self._raw.get("hostname", "ubuntu")

    @property
    def primary_user(self) -> str:
        return self._raw.get("primary_user", "ubuntu")

    @property
    def installed_packages(self) -> list:
        return self._raw.get("installed_packages", [])

    @property
    def running_services(self) -> list:
        return self._raw.get("running_services", [])

    @property
    def open_ports(self) -> list:
        return self._raw.get("open_ports", [])

    @property
    def users(self) -> list:
        return self._raw.get("users", [])

    @property
    def groups(self) -> list:
        return self._raw.get("groups", [])

    @property
    def ssh_config(self) -> dict:
        return self._raw.get("ssh_config", {})

    @property
    def cron_jobs(self) -> list:
        return self._raw.get("cron_jobs", [])

    @property
    def filesystem_manifest(self) -> dict:
        return self._raw.get("filesystem", {"entries": []})

    def package_version(self, name: str) -> Optional[str]:
        """Return the installed version for a package, or None if not installed."""
        for pkg in self.installed_packages:
            if pkg.get("name") == name:
                return pkg.get("version")
        return None

    def is_service_running(self, service: str) -> bool:
        return service in self.running_services

    # ------------------------------------------------------------------
    # MachineState — the Redis-storable representation for a session
    # ------------------------------------------------------------------

    def build_machine_state(self) -> Dict[str, str]:
        """
        Build the canonical MachineState dict for a new session.
        Only Ubuntu-related facts are included.
        Values are serialized to strings for Redis HSET compatibility.
        """
        return {
            "device_purpose": self._raw.get("device_purpose", "Ubuntu research decoy"),
            "user_roles": json.dumps(self._raw.get("user_roles", {})),
            "ubuntu_version":      self.ubuntu_version,
            "kernel_version":      self.kernel_version,
            "hostname":            self.hostname,
            "primary_user":        self.primary_user,
            "installed_packages":  json.dumps(self.installed_packages),
            "running_services":    json.dumps(self.running_services),
            "open_ports":          json.dumps(self.open_ports),
            "users":               json.dumps(self.users),
            "groups":              json.dumps(self.groups),
            "network_interfaces":  json.dumps(self._raw.get("network_interfaces", [])),
            "mounted_drives":      json.dumps(self._raw.get("mounted_drives", [])),
            "ssh_config":          json.dumps(self.ssh_config),
            "cron_jobs":           json.dumps(self.cron_jobs),
            "filesystem_manifest": json.dumps(self.filesystem_manifest),
            "created_at":          str(time.time()),
        }

    def get_or_create_machine_state(self, redis_client, session_id: str) -> Dict[str, Any]:
        """
        Returns the MachineState for a session from Redis.
        Creates it from the Ubuntu profile if it doesn't exist yet.

        The state is immutable once created — facts must not drift mid-session.
        """
        key = f"chronos:machine_state:{session_id}"
        existing = redis_client.hgetall(key)
        if existing:
            return existing

        # Profile revisions are explicit device identities, not silent updates
        # to an existing persona. This record is outside disposable fs keys.
        revision = hashlib.sha256(json.dumps(
            self._raw, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        device_key = f"chronos:device:v1:{revision}"
        proposed = self.build_machine_state()
        proposed.update(persona_schema="1", device_id=revision,
                        profile_revision=revision)
        initialize = """
        if redis.call('EXISTS', KEYS[1]) == 0 then
            for i = 1, #ARGV, 2 do
                redis.call('HSET', KEYS[1], ARGV[i], ARGV[i+1])
            end
        end
        return redis.call('HGETALL', KEYS[1])
        """
        def create_once(target, values):
            pairs = [item for pair in values.items() for item in pair]
            result = redis_client.eval(initialize, 1, target, *pairs)
            result = [v.decode() if isinstance(v, bytes) else v for v in result]
            return dict(zip(result[::2], result[1::2]))

        device = create_once(device_key, proposed)
        # Atomic first-writer-wins also prevents concurrent file reads from
        # assigning different simulation reference times to one session.
        return create_once(key, device)
