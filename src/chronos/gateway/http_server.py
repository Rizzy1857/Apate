import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict, Any, Optional
from chronos.core.logging_config import setup_logging

logger = setup_logging(__name__)


class HTTPHoneypotHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler with threat detection"""

    def __init__(self, *args, audit_callback: Optional[Callable] = None, **kwargs):
        self.audit_callback = audit_callback
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        logger.info(f"[HTTP] {format % args}")

    def _detect_threats(self, path: str, headers: Dict, body: str = "") -> Dict[str, Any]:
        """Detect common attack patterns"""
        threats = []

        sql_patterns = [
            r"(\bunion\b.*\bselect\b|\bselect\b.*\bfrom\b)",
            r"(\'|\")(\s)*(or|and)(\s)*(\d+|\'|\")(\s)*=(\s)*(\d+|\'|\")",
            r";\s*(drop|delete|insert|update)\s+",
        ]
        for pattern in sql_patterns:
            if re.search(pattern, path + body, re.IGNORECASE):
                threats.append({"type": "sql_injection", "severity": "critical"})

        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
        ]
        for pattern in xss_patterns:
            if re.search(pattern, path + body, re.IGNORECASE):
                threats.append({"type": "xss", "severity": "high"})

        if ".." in path or "etc/passwd" in path.lower():
            threats.append({"type": "directory_traversal", "severity": "high"})

        cmd_patterns = [r"[;&|`$]", r"\$\(.*\)", r"`.*`"]
        for pattern in cmd_patterns:
            if re.search(pattern, path + body):
                threats.append({"type": "command_injection", "severity": "critical"})

        return {
            "threats_detected": len(threats),
            "threats": threats,
            "risk_level": "critical" if any(t["severity"] == "critical" for t in threats) else "high" if threats else "low"
        }

    def do_GET(self):
        threat_analysis = self._detect_threats(self.path, dict(self.headers))

        if self.audit_callback:
            self.audit_callback("http_request", {
                "method": "GET",
                "path": self.path,
                "headers": dict(self.headers),
                "client": self.client_address,
                "threats": threat_analysis
            })

        if "/admin" in self.path:
            self._send_response(200, "text/html", "<h1>Admin Panel</h1>")
        elif "/api" in self.path:
            self._send_response(200, "application/json", '{"status": "ok"}')
        elif "/uploads" in self.path:
            self._send_response(200, "text/html", "<h1>Upload</h1>")
        else:
            self._send_response(200, "text/html", "<h1>Honeypot</h1>")
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8', errors='ignore')

        threat_analysis = self._detect_threats(self.path, dict(self.headers), body)

        if self.audit_callback:
            self.audit_callback("http_request", {
                "method": "POST",
                "path": self.path,
                "headers": dict(self.headers),
                "body": body[:1000],
                "client": self.client_address,
                "threats": threat_analysis
            })

        self._send_response(200, "application/json", '{"status": "received"}')
    
    def _send_response(self, code: int, content_type: str, content: str):
        self.send_response(code)
        self.send_header('Content-type', content_type)
        self.send_header('Server', 'Apache/2.4.41')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))


class HTTPHoneypot:
    """HTTP Honeypot Server with threat detection"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, audit_callback: Optional[Callable] = None):
        self.host = host
        self.port = port
        self.audit_callback = audit_callback
        self.server = None
        self.thread = None
        
    def _handler_factory(self, *args, **kwargs):
        return HTTPHoneypotHandler(*args, audit_callback=self.audit_callback, **kwargs)

    def start(self):
        try:
            self.server = HTTPServer((self.host, self.port), self._handler_factory)
            logger.info(f"HTTP Honeypot starting on {self.host}:{self.port}")
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
        except Exception as e:
            logger.error(f"HTTP Honeypot start failed: {e}")
            raise

    def stop(self):
        if self.server:
            logger.info("HTTP Honeypot shutting down")
            self.server.shutdown()
            self.server.server_close()
            if self.thread:
                self.thread.join(timeout=5)
            logger.info("[HTTP Honeypot] Server stopped")


if __name__ == "__main__":
    def audit_log(event_type, data):
        logger.info(f"[AUDIT] {event_type}: {data}")
    
    honeypot = HTTPHoneypot(port=8080, audit_callback=audit_log)
    honeypot.start()
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        honeypot.stop()
