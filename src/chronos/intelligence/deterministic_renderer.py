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
            "/etc/ssl/certs/ssl-cert-snakeoil.pem": self._render_snakeoil_cert,
            "/etc/ssl/private/ssl-cert-snakeoil.key": self._render_snakeoil_key,
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

    def _snakeoil_pair(self, ms):
        """Public, reproducible decoy material. NEVER use for real TLS services."""
        import hashlib
        from datetime import datetime, timezone
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.x509.oid import NameOID
        hostname = ms.get("hostname", "ubuntu")
        seed = hashlib.sha256(("apate-public-decoy-v1:" + hostname).encode()).digest()
        key = Ed25519PrivateKey.from_private_bytes(seed)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key())
                .serial_number(int.from_bytes(seed[:19], "big") or 1)
                .not_valid_before(datetime(2024, 1, 1, tzinfo=timezone.utc))
                .not_valid_after(datetime(2034, 1, 1, tzinfo=timezone.utc))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .sign(key, algorithm=None))
        return (cert.public_bytes(serialization.Encoding.PEM),
                key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))

    def _render_snakeoil_cert(self, ms: Dict[str, Any]) -> bytes:
        return self._snakeoil_pair(ms)[0]

    def _render_snakeoil_key(self, ms: Dict[str, Any]) -> bytes:
        return self._snakeoil_pair(ms)[1]
