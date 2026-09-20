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

    def _render_snakeoil_cert(self, ms: Dict[str, Any]) -> bytes:
        return (
            b"-----BEGIN CERTIFICATE-----\n"
            b"MIIDBzCCAe+gAwIBAgIUBbXyG8oO+0/J5tDq6eQ8y6L+OQwwDQYJKoZIhvcNAQEL\n"
            b"BQAwFjEUMBIGA1UEAwwLd2ViMDEubG9jYWwwHhcNMjMwOTA1MDAwMDAwWhcNMzMw\n"
            b"OTA1MDAwMDAwWjAWMRQwEgYDVQQDDAt3ZWIwMS5sb2NhbDCCASIwDQYJKoZIhvcN\n"
            b"AQEBBQADggEPADCCAQoCggEBALk/0e6K9vO8WlGqJ3n6lDkH9gZ5r2m6mQz+B5xM\n"
            b"9tQ4b+O1rC5k6R3lY/qPq9qY+pW9zZ9x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q\n"
            b"1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE\n"
            b"2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7\n"
            b"lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x\n"
            b"0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W\n"
            b"6FqE2wM0+D/7lJqG/ZAgMBAAGjUzBRMB0GA1UdDgQWBBQy9s7q+3T7w9y1mO9w2s\n"
            b"8M7Q4Q6jAfBgNVHSMEGDAWgBQy9s7q+3T7w9y1mO9w2s8M7Q4Q6jAPBgNVHRMBAf8E\n"
            b"BTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQC0+O8WlGqJ3n6lDkH9gZ5r2m6mQz+B\n"
            b"5xM9tQ4b+O1rC5k6R3lY/qPq9qY+pW9zZ9x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x\n"
            b"0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W\n"
            b"6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0\n"
            b"+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7lJq\n"
            b"G/Z5x0o8Q1p8W6FqE2wM0+D/7lJqG/Z5x0o8Q1p8W6FqE2wM0+D/7l\n"
            b"-----END CERTIFICATE-----\n"
        )
        
    def _render_snakeoil_key(self, ms: Dict[str, Any]) -> bytes:
        return (
            b"-----BEGIN PRIVATE KEY-----\n"
            b"MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC5P9HuivbzvFpR\n"
            b"qid5+pQ5B/YGea9pupkM/gecTPbUOG/jtawuZOkd5WP6j6vamPqVvc2fcdKPEPaf\n"
            b"FuhahNsDNPg/+5Sahv2ecdKPEPafFuhahNsDNPg/+5Sahv2ecdKPEPafFuhahNsD\n"
            b"NPg/+5Sahv2ecdKPEPafFuhahNsDNPg/+5Sahv2ecdKPEPafFuhahNsDNPg/+5Sa\n"
            b"hv2ecdKPEPafFuhahNsDNPg/+5Sahv2ecdKPEPafFuhahNsDNPg/+5Sahv2ecdKP\n"
            b"EPafFuhahNsDNPg/+5Sahv2ecdKPEPafFuhahNsDNPg/+5Sahv2ecdKPEPafFuha\n"
            b"hNsDNPg/+5Sahv2ecdKPEPafFuhahNsDNPg/+5Sahv2QIBAQKBgQC3/X8Y3V6T9\n"
            b"8J9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L\n"
            b"6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T\n"
            b"9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T\n"
            b"4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F\n"
            b"4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O\n"
            b"3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6QKBgQ\n"
            b"Dz3L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0\n"
            b"L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3\n"
            b"G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9\n"
            b"N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8\n"
            b"L1H5N9V9L6QKBgQDC9L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5\n"
            b"N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8\n"
            b"H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9\n"
            b"V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3\n"
            b"X6QKBgQDS+L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4\n"
            b"O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4\n"
            b"W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3\n"
            b"H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6QKBgQC3PL1H5N9V9L6T4O3H2B0\n"
            b"L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3\n"
            b"G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9\n"
            b"N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8\n"
            b"L1H5N9V9L6QKBgQCmAL1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5\n"
            b"N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8\n"
            b"H3X6T9F4W0Y5O3G8L1H5N9V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9\n"
            b"V9L6T4O3H2B0L9N5J9V8H3X6T9F4W0Y5O3G8L1H5N9V9L6\n"
            b"-----END PRIVATE KEY-----\n"
        )

