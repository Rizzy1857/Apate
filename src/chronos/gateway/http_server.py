"""
HTTP Honeypot Server
Simulates vulnerable web applications to attract and analyze HTTP-based attacks
"""
import logging
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict, Any, Optional
from urllib.parse import parse_qs, urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HTTPHoneypotHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler with threat detection"""
    
    def __init__(self, *args, audit_callback: Optional[Callable] = None, **kwargs):
        self.audit_callback = audit_callback
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to use custom logging"""
        logger.info(f"[HTTP] {format % args}")
    
    def _detect_threats(self, path: str, headers: Dict, body: str = "") -> Dict[str, Any]:
        """Detect common attack patterns"""
        threats = []
        
        # SQL Injection patterns
        sql_patterns = [
            r"(\bunion\b.*\bselect\b|\bselect\b.*\bfrom\b)",
            r"(\'|\")(\s)*(or|and)(\s)*(\d+|\'|\")(\s)*=(\s)*(\d+|\'|\")",
            r";\s*(drop|delete|insert|update)\s+",
        ]
        for pattern in sql_patterns:
            if re.search(pattern, path + body, re.IGNORECASE):
                threats.append({
                    "type": "sql_injection",
                    "severity": "critical",
                    "pattern": pattern
                })
        
        # XSS patterns
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
        ]
        for pattern in xss_patterns:
            if re.search(pattern, path + body, re.IGNORECASE):
                threats.append({
                    "type": "xss",
                    "severity": "high",
                    "pattern": pattern
                })
        
        # Directory traversal
        if ".." in path or "etc/passwd" in path.lower():
            threats.append({
                "type": "directory_traversal",
                "severity": "high",
                "indicator": path
            })
        
        # Command injection
        cmd_patterns = [r"[;&|`$]", r"\$\(.*\)", r"`.*`"]
        for pattern in cmd_patterns:
            if re.search(pattern, path + body):
                threats.append({
                    "type": "command_injection",
                    "severity": "critical",
                    "pattern": pattern
                })
        
        return {
            "threats_detected": len(threats),
            "threats": threats,
            "risk_level": "critical" if any(t["severity"] == "critical" for t in threats) else "high" if threats else "low"
        }
    
    def do_GET(self):
        """Handle GET requests"""
        threat_analysis = self._detect_threats(self.path, dict(self.headers))
        
        if self.audit_callback:
            self.audit_callback("http_request", {
                "method": "GET",
                "path": self.path,
                "headers": dict(self.headers),
                "client": self.client_address,
                "threats": threat_analysis
            })
        
        # Simulate vulnerable endpoints
        if "/admin" in self.path:
            self._send_response(200, "text/html", "<h1>Admin Panel</h1><p>Login required</p>")
        elif "/uploads" in self.path:
            self._send_response(200, "text/html", "<h1>File Upload</h1><form method='POST' enctype='multipart/form-data'><input type='file' name='file'><input type='submit'></form>")
        elif "/api" in self.path:
            self._send_response(200, "application/json", '{"status": "ok", "version": "1.0"}')
        else:
            self._send_response(200, "text/html", "<h1>Welcome</h1><p>Server running</p>")
    
    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8', errors='ignore')
        
        threat_analysis = self._detect_threats(self.path, dict(self.headers), body)
        
        if self.audit_callback:
            self.audit_callback("http_request", {
                "method": "POST",
                "path": self.path,
                "headers": dict(self.headers),
                "body": body[:1000],  # Limit body logging
                "client": self.client_address,
                "threats": threat_analysis
            })
        
        self._send_response(200, "application/json", '{"status": "received"}')
    
    def _send_response(self, code: int, content_type: str, content: str):
        """Send HTTP response"""
        self.send_response(code)
        self.send_header('Content-type', content_type)
        self.send_header('Server', 'Apache/2.4.41 (Ubuntu)')  # Fake server header
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))


class HTTPHoneypot:
    """
    HTTP Honeypot Server
    Provides simulated web services to analyze HTTP-based attacks
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080, audit_callback: Optional[Callable] = None):
        """
        Args:
            host: Interface to bind to
            port: Port to listen on
            audit_callback: Function to call with audit events
        """
        self.host = host
        self.port = port
        self.audit_callback = audit_callback
        self.server = None
        self.thread = None
        
    def _handler_factory(self, *args, **kwargs):
        """Factory to inject audit_callback into handler"""
        return HTTPHoneypotHandler(*args, audit_callback=self.audit_callback, **kwargs)
    
    def start(self):
        """Start the HTTP honeypot server"""
        try:
            self.server = HTTPServer((self.host, self.port), self._handler_factory)
            logger.info(f"[HTTP Honeypot] Starting server on {self.host}:{self.port}")
            
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info("[HTTP Honeypot] Server started successfully")
            
        except Exception as e:
            logger.error(f"[HTTP Honeypot] Failed to start server: {e}")
            raise
    
    def stop(self):
        """Stop the HTTP honeypot server"""
        if self.server:
            logger.info("[HTTP Honeypot] Shutting down server")
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
