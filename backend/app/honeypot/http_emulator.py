"""
HTTP Emulator
-------------
Simulates realistic HTTP services with adaptive login pages and responses.
Includes honeytoken deployment and request logging for threat intelligence.
"""

import logging
import random
import hashlib
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from ..data_logger import log_outcome

logger = logging.getLogger(__name__)

class HTTPSession:
    """Manages HTTP session state and tracking"""
    
    def __init__(self, session_id: str, source_ip: str):
        self.session_id = session_id
        self.source_ip = source_ip
        self.created_at = datetime.now(UTC)
        self.login_attempts = []
        self.pages_accessed = []
        self.user_agent: Optional[str] = None
        self.is_suspicious = False
        self.threat_score = 0.0

class HTTPEmulator:
    """HTTP honeypot emulator with adaptive responses"""
    
    def __init__(self):
        self.sessions: Dict[str, HTTPSession] = {}
        self.failed_login_tracking: Dict[str, List[datetime]] = {}
        self.honeytoken_credentials = self._load_honeytoken_credentials()
        
        # Realistic service banners and responses
        self.service_banners = {
            "apache": "Apache/2.4.41 (Ubuntu)",
            "nginx": "nginx/1.18.0 (Ubuntu)",
            "iis": "Microsoft-IIS/10.0"
        }
        
        # Common login page templates
        self.login_templates = {
            "admin_panel": self._get_admin_panel_template(),
            "webmail": self._get_webmail_template(),
            "ftp_web": self._get_ftp_web_template(),
            "router": self._get_router_template()
        }
    
    def _load_honeytoken_credentials(self) -> List[Dict[str, str]]:
        """Load honeytoken credentials for detection"""
        return [
            {"username": "admin", "password": "admin"},
            {"username": "admin", "password": "password"},
            {"username": "admin", "password": "12345"},
            {"username": "root", "password": "root"},
            {"username": "administrator", "password": "administrator"},
            {"username": "user", "password": "user"},
            {"username": "guest", "password": "guest"},
            {"username": "test", "password": "test"},
            {"username": "demo", "password": "demo"},
            # Honeytoken - these trigger high-priority alerts
            {"username": "backup_admin", "password": "B@ckup2023!"},
            {"username": "api_service", "password": "ApiKey_Secret_2023"},
            {"username": "db_readonly", "password": "ReadOnly_DB_Access"},
        ]
    
    async def handle_login(self, username: str, password: str, source_ip: str, 
                          user_agent: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Process HTTP login attempt with adaptive response"""
        
        if not session_id:
            session_id = hashlib.md5(f"{source_ip}_{datetime.now(UTC)}".encode()).hexdigest()
        
        # Get or create session
        if session_id not in self.sessions:
            self.sessions[session_id] = HTTPSession(session_id, source_ip)
        
        session = self.sessions[session_id]
        session.user_agent = user_agent
        
        # Log login attempt
        attempt = {
            "username": username,
            "password": password,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_agent": user_agent,
            "success": False
        }
        session.login_attempts.append(attempt)
        
        # Track failed logins for rate limiting simulation (per IP)
        now = datetime.now(UTC)
        if source_ip not in self.failed_login_tracking:
            self.failed_login_tracking[source_ip] = []
        # Record every attempt (failed by default in this honeypot)
        self.failed_login_tracking[source_ip].append(now)
        
        # Log the attempt
        logger.info(f"HTTP Login attempt from {source_ip}: {username}:{password}")
        
        # Check for honeytoken credentials
        is_honeytoken = self._is_honeytoken_credential(username, password)
        if is_honeytoken:
            logger.critical(f"HONEYTOKEN TRIGGERED: {username}:{password} from {source_ip}")
            return await self._handle_honeytoken_login(session, username, password)
        
        # Check for common credential attacks
        threat_level = self._assess_threat_level(session, username, password)
        
        # Simulate realistic login behavior based on threat level
        if threat_level == "high":
            return await self._handle_high_threat_login(session, username, password)
        elif threat_level == "medium":
            return await self._handle_medium_threat_login(session, username, password)
        else:
            return await self._handle_normal_login(session, username, password)
    
    def _is_honeytoken_credential(self, username: str, password: str) -> bool:
        """Check if credentials match honeytoken patterns"""
        # High-value honeytokens that should trigger immediate alerts
        honeytoken_patterns = [
            "backup_admin", "api_service", "db_readonly", "service_account",
            "monitoring", "nagios", "zabbix", "splunk"
        ]
        
        return any(pattern in username.lower() for pattern in honeytoken_patterns)
    
    def _assess_threat_level(self, session: HTTPSession, username: str, password: str) -> str:
        """Assess threat level based on login patterns"""
        score = 0
        
        # Rapid successive attempts
        recent_attempts = [a for a in session.login_attempts 
                          if datetime.fromisoformat(a["timestamp"]) > datetime.now(UTC) - timedelta(minutes=5)]
        if len(recent_attempts) > 10:
            score += 3
        elif len(recent_attempts) > 5:
            score += 2

        # Per-IP brute force across sessions
        ip_failures = self.failed_login_tracking.get(session.source_ip, [])
        ip_recent_failures = [t for t in ip_failures if t > datetime.now(UTC) - timedelta(minutes=5)]
        if len(ip_recent_failures) > 12:
            score += 5
        elif len(ip_recent_failures) > 8:
            score += 4
        elif len(ip_recent_failures) > 5:
            score += 3
        elif len(ip_recent_failures) > 3:
            score += 2
        
        # Common attack usernames
        attack_usernames = ["admin", "administrator", "root", "user", "guest", "test"]
        if username.lower() in attack_usernames:
            score += 1
        
        # Weak passwords
        weak_passwords = ["password", "123456", "admin", "root", "guest"]
        if password.lower() in weak_passwords:
            score += 1

        # Combination of common admin username + weak password should be elevated
        if username.lower() in ["admin", "administrator", "root"] and password.lower() in weak_passwords:
            score += 1
        
        # Suspicious user agents
        if session.user_agent:
            suspicious_agents = ["curl", "wget", "python", "scanner", "bot"]
            if any(agent in session.user_agent.lower() for agent in suspicious_agents):
                score += 2
        
        if score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"
    
    async def _handle_honeytoken_login(self, session: HTTPSession, username: str, password: str) -> Dict[str, Any]:
        """Handle honeytoken credential usage - high priority alert"""
        session.threat_score = 10.0
        session.is_suspicious = True
        # Log outcome signal for analysis
        try:
            log_outcome(
                session_id=session.session_id,
                session_duration_bucket="1-5m",
                honeytoken_triggered=True,
                protocol_switched=False,
                repeated_after_error=False,
                abandoned_after_delay=False,
            )
        except Exception:
            pass
        
        # Simulate successful login to keep attacker engaged
        return {
            "success": True,
            "message": "Login successful",
            "session_token": f"ht_{session.session_id}",
            "redirect_url": "/dashboard",
            "user_role": "admin",
            "server": random.choice(list(self.service_banners.values())),
            "alert_level": "CRITICAL",
            "honeytoken_triggered": True,
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    async def _handle_high_threat_login(self, session: HTTPSession, username: str, password: str) -> Dict[str, Any]:
        """Handle high-threat login attempts"""
        session.threat_score += 2.0
        
        # Simulate account lockout or rate limiting
        recent_failures = [
            t for t in self.failed_login_tracking[session.source_ip]
            if t > datetime.now(UTC) - timedelta(minutes=15)
        ]
        
        if len(recent_failures) > 5:
            logger.warning(f"Rate limiting triggered for {session.source_ip}")
            return {
                "success": False,
                "error": "Account temporarily locked due to multiple failed attempts",
                "retry_after": 900,  # 15 minutes
                "server": random.choice(list(self.service_banners.values())),
                "alert_level": "HIGH",
                "timestamp": datetime.now(UTC).isoformat()
            }
        
        # Random realistic error messages
        error_messages = [
            "Invalid username or password",
            "Authentication failed",
            "Login credentials incorrect",
            "Access denied"
        ]
        
        return {
            "success": False,
            "error": random.choice(error_messages),
            "server": random.choice(list(self.service_banners.values())),
            "alert_level": "HIGH",
            "attempts_remaining": max(0, 5 - len(recent_failures)),
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    async def _handle_medium_threat_login(self, session: HTTPSession, username: str, password: str) -> Dict[str, Any]:
        """Handle medium-threat login attempts"""
        session.threat_score += 1.0
        
        # Occasionally simulate partial success to keep attacker interested
        if random.random() < 0.1:  # 10% chance
            return {
                "success": False,
                "error": "Password expired. Please contact administrator.",
                "server": random.choice(list(self.service_banners.values())),
                "alert_level": "MEDIUM",
                "password_expired": True,
                "timestamp": datetime.now(UTC).isoformat()
            }
        
        return {
            "success": False,
            "error": "Invalid credentials",
            "server": random.choice(list(self.service_banners.values())),
            "alert_level": "MEDIUM",
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    async def _handle_normal_login(self, session: HTTPSession, username: str, password: str) -> Dict[str, Any]:
        """Handle normal/low-threat login attempts"""
        # Rarely simulate success for realistic behavior
        if random.random() < 0.02:  # 2% chance
            return {
                "success": True,
                "message": "Login successful",
                "session_token": f"demo_{session.session_id}",
                "redirect_url": "/welcome",
                "user_role": "user",
                "server": random.choice(list(self.service_banners.values())),
                "alert_level": "LOW",
                "timestamp": datetime.now(UTC).isoformat()
            }
        
        return {
            "success": False,
            "error": "Invalid username or password",
            "server": random.choice(list(self.service_banners.values())),
            "alert_level": "LOW",
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    def _get_admin_panel_template(self) -> str:
        """Admin panel login page template"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Admin Panel - Login</title></head>
        <body>
        <h2>Administrator Login</h2>
        <form method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        </body>
        </html>
        """
    
    def _get_webmail_template(self) -> str:
        """Webmail login page template"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Webmail Access</title></head>
        <body>
        <h2>Email Login</h2>
        <form method="post">
            <input type="email" name="username" placeholder="Email Address" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Sign In</button>
        </form>
        </body>
        </html>
        """
    
    def _get_ftp_web_template(self) -> str:
        """FTP web interface template"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>FTP Web Access</title></head>
        <body>
        <h2>FTP File Manager</h2>
        <form method="post">
            <input type="text" name="username" placeholder="FTP Username" required>
            <input type="password" name="password" placeholder="FTP Password" required>
            <button type="submit">Connect</button>
        </form>
        </body>
        </html>
        """
    
    def _get_router_template(self) -> str:
        """Router admin interface template"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Router Configuration</title></head>
        <body>
        <h2>Router Admin Panel</h2>
        <form method="post">
            <input type="text" name="username" placeholder="Admin Username" required>
            <input type="password" name="password" placeholder="Admin Password" required>
            <button type="submit">Login</button>
        </form>
        </body>
        </html>
        """
    
    async def get_login_page(self, page_type: str = "admin_panel") -> str:
        """Return appropriate login page template"""
        return self.login_templates.get(page_type, self.login_templates["admin_panel"])
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information for analysis"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            return {
                "session_id": session.session_id,
                "source_ip": session.source_ip,
                "created_at": session.created_at.isoformat(),
                "login_attempts": len(session.login_attempts),
                "threat_score": session.threat_score,
                "is_suspicious": session.is_suspicious,
                "user_agent": session.user_agent
            }
        return None
