import json
from typing import Dict, Any

class DeterministicRenderer:
    """
    Renders deterministic system files purely from MachineState without AI intervention.
    Used for 'deterministic' class files in the filesystem manifest.
    """
    
    def render(self, path: str, machine_state: Dict[str, Any]) -> bytes:
        handlers = {
            "/etc/passwd": self._render_passwd,
            "/etc/group": self._render_group,
            "/etc/hostname": self._render_hostname,
            "/etc/hosts": self._render_hosts,
            "/etc/os-release": self._render_os_release,
            "/etc/fstab": self._render_fstab,
            "/etc/resolv.conf": self._render_resolv_conf,
            "/etc/ssh/sshd_config": self._render_sshd_config,
        }
        
        handler = handlers.get(path)
        if handler:
            return handler(machine_state)
        return b""
            
    def _render_passwd(self, ms: Dict[str, Any]) -> bytes:
        try:
            users = json.loads(ms.get("users", "[]"))
        except json.JSONDecodeError:
            users = []
            
        lines = []
        for u in users:
            name = u.get("name", "unknown")
            uid = u.get("uid", 1000)
            gid = u.get("gid", 1000)
            home = u.get("home", f"/home/{name}")
            shell = u.get("shell", "/bin/bash")
            gecos = u.get("gecos", name.capitalize())
            lines.append(f"{name}:x:{uid}:{gid}:{gecos}:{home}:{shell}")
        return ("\n".join(lines) + "\n").encode("utf-8")
        
    def _render_group(self, ms: Dict[str, Any]) -> bytes:
        try:
            groups = json.loads(ms.get("groups", "[]"))
        except json.JSONDecodeError:
            groups = []
            
        lines = []
        for g in groups:
            name = g.get("name", "unknown")
            gid = g.get("gid", 1000)
            members = ",".join(g.get("members", []))
            lines.append(f"{name}:x:{gid}:{members}")
        return ("\n".join(lines) + "\n").encode("utf-8")
        
    def _render_hostname(self, ms: Dict[str, Any]) -> bytes:
        hostname = ms.get("hostname", "ubuntu")
        return f"{hostname}\n".encode("utf-8")
        
    def _render_hosts(self, ms: Dict[str, Any]) -> bytes:
        hostname = ms.get("hostname", "ubuntu")
        return f"127.0.0.1\tlocalhost\n127.0.1.1\t{hostname}\n".encode("utf-8")
        
    def _render_os_release(self, ms: Dict[str, Any]) -> bytes:
        version = ms.get("ubuntu_version", "24.04")
        return f'PRETTY_NAME="Ubuntu {version} LTS"\nNAME="Ubuntu"\nVERSION_ID="{version}"\n'.encode("utf-8")
        
    def _render_fstab(self, ms: Dict[str, Any]) -> bytes:
        try:
            drives = json.loads(ms.get("mounted_drives", "[]"))
        except json.JSONDecodeError:
            drives = []
            
        lines = ["# /etc/fstab: static file system information."]
        for d in drives:
            dev = d.get("device", "none")
            mp = d.get("mountpoint", "/")
            fstype = d.get("fstype", "ext4")
            lines.append(f"{dev}\t{mp}\t{fstype}\tdefaults\t0\t0")
        return ("\n".join(lines) + "\n").encode("utf-8")
        
    def _render_resolv_conf(self, ms: Dict[str, Any]) -> bytes:
        return b"nameserver 8.8.8.8\nnameserver 8.8.4.4\n"
        
    def _render_sshd_config(self, ms: Dict[str, Any]) -> bytes:
        try:
            ssh_config = json.loads(ms.get("ssh_config", "{}"))
        except json.JSONDecodeError:
            ssh_config = {}
            
        port = ssh_config.get("port", 22)
        permit_root = "yes" if ssh_config.get("permit_root_login") else "no"
        pwd_auth = "yes" if ssh_config.get("password_authentication") else "no"
        return f"Port {port}\nPermitRootLogin {permit_root}\nPasswordAuthentication {pwd_auth}\n".encode("utf-8")
