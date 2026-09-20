from chronos.intelligence.artifact_policy import ArtifactPolicy
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
            hostname = escape(str((machine_state or {}).get('hostname', 'web01')))
            return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                    f'<title>{hostname}</title></head>\n<body><h1>{hostname}</h1>'
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
