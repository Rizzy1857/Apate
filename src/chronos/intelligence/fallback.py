from chronos.intelligence.artifact_policy import ArtifactPolicy
from datetime import datetime, timezone
from html import escape

class FallbackProvider:
    """
    Provides degraded content when the Circuit Breaker is OPEN or when validation fails.
    This replaces hardcoded static templates inside the orchestrator, giving a clean
    boundary for future caching or procedural fallback strategies.
    """
    def __init__(self):
        pass

    def get_degraded_content(self, filename: str, policy: ArtifactPolicy,
                             path: str = '', machine_state=None) -> bytes:
        """
        Returns a minimal static template for the file class.
        The template must never look like an AI fallback to an attacker.
        """
        machine = machine_state or {}
        hostname = str(machine.get('hostname', 'web01'))
        primary_user = str(machine.get('primary_user', 'ubuntu'))
        try:
            reference = datetime.fromtimestamp(
                float(machine.get('created_at', 0)), timezone.utc
            )
        except (TypeError, ValueError, OSError):
            reference = datetime.fromtimestamp(0, timezone.utc)
        syslog_stamp = reference.strftime('%b %e %H:%M:%S')

        if path == '/var/log/auth.log':
            return (
                f'{syslog_stamp} {hostname} sshd[842]: Server listening on 0.0.0.0 port 22.\n'
                f'{syslog_stamp} {hostname} sshd[842]: Server listening on :: port 22.\n'
                f'{syslog_stamp} {hostname} systemd-logind[611]: New seat seat0.\n'
            ).encode()
        if path == '/var/log/syslog':
            return (
                f'{syslog_stamp} {hostname} systemd[1]: Started nginx.service - A high performance web server.\n'
                f'{syslog_stamp} {hostname} systemd[1]: Started ssh.service - OpenBSD Secure Shell server.\n'
                f'{syslog_stamp} {hostname} cron[735]: (CRON) INFO (Running @reboot jobs)\n'
            ).encode()
        if path == f'/home/{primary_user}/.bash_history':
            return (
                'sudo systemctl status nginx\n'
                'sudo nginx -t\n'
                'journalctl -u nginx --since today\n'
                'df -h\n'
                'ss -lnt\n'
            ).encode()
        if path == f'/home/{primary_user}/notes.txt':
            return (
                'Maintenance notes\n'
                '- Review nginx access logs after the next restart.\n'
                '- Confirm certificate renewal timer is active.\n'
                '- Apply routine package updates during the maintenance window.\n'
            ).encode()
        if path == '/etc/nginx/nginx.conf':
            return (b'user www-data;\nworker_processes auto;\n'
                    b'pid /run/nginx.pid;\nevents { worker_connections 1024; }\n'
                    b'http {\n    default_type text/html;\n'
                    b'    access_log /var/log/nginx/access.log;\n'
                    b'    error_log /var/log/nginx/error.log;\n'
                    b'    server {\n        listen 80;\n'
                    b'        listen 443 ssl;\n'
                    b'        ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;\n'
                    b'        ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;\n'
                    b'        server_name _;\n'
                    b'        root /var/www/html;\n        index index.html;\n'
                    b'        location / { try_files $uri $uri/ =404; }\n    }\n}\n')
        if path == '/var/www/html/index.html':
            safe_hostname = escape(hostname)
            return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                    f'<title>{safe_hostname}</title></head>\n<body><h1>{safe_hostname}</h1>'
                    '<p>Service available.</p></body></html>\n').encode()
        templates = {
            "config_file": b"# configuration file\n",
            "log_file": b"",
            "credential_file": b"",
            "history_file": b"",
            "notes_file": b"",
            "script_file": b"#!/bin/bash\n",
            "temp_file": b"",
        }
        return templates.get(policy.file_class, b"")
