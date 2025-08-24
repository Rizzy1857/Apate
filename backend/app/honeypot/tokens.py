"""
Honeytoken Generator
-------------------
Creates and manages honeytokens for detecting attacker activity.
Generates realistic but fake credentials, API keys, and files.
"""

import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class HoneytokenType:
    """Types of honeytokens that can be generated"""
    CREDENTIALS = "credentials"
    API_KEY = "api_key"
    FILE = "file"
    CONFIG = "config"
    DATABASE = "database"
    SSH_KEY = "ssh_key"
    WEB_BEACON = "web_beacon"

class HoneytokenGenerator:
    """Generates various types of honeytokens"""
    
    def __init__(self):
        self.active_tokens: Dict[str, Dict[str, Any]] = {}
        self.triggered_tokens: List[Dict[str, Any]] = []
        
    def generate_credentials(self, service_type: str = "generic") -> Dict[str, str]:
        """Generate realistic looking credentials"""
        service_patterns = {
            "database": {
                "usernames": ["db_admin", "readonly_user", "backup_service", "monitor_user"],
                "password_pattern": "db_{adjective}_{number}!"
            },
            "api": {
                "usernames": ["api_service", "api_user", "api_admin"],
                "password_pattern": "API_{random}_{year}"
            },
            "backup": {
                "usernames": ["backup_admin", "backup_service", "archive_user"],
                "password_pattern": "Backup_{month}_{day}!"
            },
            "monitoring": {
                "usernames": ["monitor_admin", "monitor_service", "monitor_user", "health_admin"],
                "password_pattern": "Monitor_{random}_2023"
            }
        }
        
        pattern = service_patterns.get(service_type, {
            "usernames": ["service_account", "admin_backup", "system_user"],
            "password_pattern": "Service_{random}_{year}!"
        })
        
        username = random.choice(pattern["usernames"])
        password = self._generate_password_from_pattern(pattern["password_pattern"])
        
        token_id = self._generate_token_id()
        
        credential = {
            "username": username,
            "password": password,
            "service_type": service_type,
            "token_id": token_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed": False
        }
        
        self.active_tokens[token_id] = credential
        logger.info(f"Generated credential honeytoken: {username} for {service_type}")
        
        return credential
    
    def generate_api_key(self, provider: str = "generic") -> Dict[str, str]:
        """Generate realistic API keys"""
        api_patterns = {
            "aws": "AKIA{random_upper_16}",
            "openai": "sk-{random_lower_48}",
            "stripe": "sk_live_{random_lower_24}",
            "github": "ghp_{random_mixed_36}",
            "slack": "xoxb-{random_numbers_12}-{random_numbers_12}-{random_mixed_24}",
            "generic": "api_{random_lower_32}"
        }
        
        pattern = api_patterns.get(provider, api_patterns["generic"])
        api_key = self._generate_key_from_pattern(pattern)
        
        token_id = self._generate_token_id()
        
        api_token = {
            "api_key": api_key,
            "provider": provider,
            "token_id": token_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed": False,
            "permissions": "read-write" if provider != "generic" else "read-only"
        }
        
        self.active_tokens[token_id] = api_token
        logger.info(f"Generated API key honeytoken for {provider}")
        
        return api_token
    
    def generate_ssh_key(self) -> Dict[str, str]:
        """Generate fake SSH key pair"""
        # Generate fake SSH private key format
        private_key = f"""-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAFwAAAAdzc2gtcn
NhAAAAAwEAAQAAAQEA{self._generate_base64_string(256)}
{self._generate_base64_string(64)}
{self._generate_base64_string(64)}
-----END OPENSSH PRIVATE KEY-----"""
        
        # Generate corresponding public key
        public_key = f"ssh-rsa AAAAB3NzaC1yc2E{self._generate_base64_string(372)} admin@honeypot-server"
        
        token_id = self._generate_token_id()
        
        ssh_token = {
            "private_key": private_key,
            "public_key": public_key,
            "token_id": token_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed": False,
            "key_type": "rsa",
            "key_size": 2048
        }
        
        self.active_tokens[token_id] = ssh_token
        logger.info("Generated SSH key honeytoken")
        
        return ssh_token
    
    def generate_config_file(self, config_type: str = "database") -> Dict[str, str]:
        """Generate configuration files with honeytokens"""
        config_templates = {
            "database": {
                "filename": ".env",
                "content": f"""# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=production_db
DB_USER=admin
DB_PASSWORD={self._generate_password_from_pattern("Prod_{random}_{year}!")}
DB_SSL_MODE=require

# Redis Configuration  
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD={self._generate_password_from_pattern("Redis_{random}_2023")}

# API Keys
STRIPE_SECRET_KEY={self.generate_api_key("stripe")["api_key"]}
OPENAI_API_KEY={self.generate_api_key("openai")["api_key"]}
"""
            },
            "aws": {
                "filename": "aws_credentials",
                "content": f"""[default]
aws_access_key_id = {self.generate_api_key("aws")["api_key"]}
aws_secret_access_key = {self._generate_key_from_pattern("secret_key_40")}
region = us-east-1

[production]
aws_access_key_id = {self.generate_api_key("aws")["api_key"]}
aws_secret_access_key = {self._generate_key_from_pattern("secret_key_40")}
region = us-west-2
"""
            },
            "docker": {
                "filename": "docker-compose.yml",
                "content": f"""version: '3.8'
services:
  app:
    image: myapp:latest
    environment:
      - DATABASE_URL=postgresql://admin:{self._generate_password_from_pattern("Docker_{random}!")}@db:5432/myapp
      - API_KEY={self.generate_api_key()["api_key"]}
      - SECRET_KEY={self._generate_key_from_pattern("secret_32")}
    ports:
      - "8080:8080"
"""
            }
        }
        
        template = config_templates.get(config_type, config_templates["database"])
        token_id = self._generate_token_id()
        
        config_token = {
            "filename": template["filename"],
            "content": template["content"],
            "config_type": config_type,
            "token_id": token_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed": False
        }
        
        self.active_tokens[token_id] = config_token
        logger.info(f"Generated config file honeytoken: {template['filename']}")
        
        return config_token
    
    def generate_web_beacon(self, callback_url: str) -> Dict[str, str]:
        """Generate web beacon for tracking token usage"""
        beacon_id = self._generate_token_id()
        
        # Create tracking pixel HTML
        beacon_html = f'''<img src="{callback_url}/beacon/{beacon_id}.gif" width="1" height="1" style="display:none;" />'''
        
        # Create tracking script
        beacon_script = f'''<script>
fetch("{callback_url}/beacon/{beacon_id}/track", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{
        beacon_id: "{beacon_id}",
        timestamp: Date.now(),
        user_agent: navigator.userAgent,
        referrer: document.referrer
    }})
}});
</script>'''
        
        token_id = self._generate_token_id()
        
        beacon_token = {
            "beacon_id": beacon_id,
            "callback_url": callback_url,
            "html_beacon": beacon_html,
            "script_beacon": beacon_script,
            "token_id": token_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accessed": False
        }
        
        self.active_tokens[token_id] = beacon_token
        logger.info(f"Generated web beacon honeytoken: {beacon_id}")
        
        return beacon_token
    
    def _generate_token_id(self) -> str:
        """Generate unique token identifier"""
        return f"ht_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{random.randint(10000, 99999)}"
    
    def _generate_password_from_pattern(self, pattern: str) -> str:
        """Generate password from pattern template"""
        adjectives = ["secure", "strong", "complex", "advanced", "premium"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        replacements = {
            "{adjective}": random.choice(adjectives),
            "{number}": str(random.randint(100, 999)),
            "{random}": ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
            "{year}": str(datetime.now().year),
            "{month}": random.choice(months),
            "{day}": str(random.randint(1, 28))
        }
        
        result = pattern
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        
        return result
    
    def _generate_key_from_pattern(self, pattern: str) -> str:
        """Generate API key from pattern template"""
        if "{random_upper_16}" in pattern:
            pattern = pattern.replace("{random_upper_16}", ''.join(random.choices(string.ascii_uppercase + string.digits, k=16)))
        if "{random_lower_48}" in pattern:
            pattern = pattern.replace("{random_lower_48}", ''.join(random.choices(string.ascii_lowercase + string.digits, k=48)))
        if "{random_lower_24}" in pattern:
            pattern = pattern.replace("{random_lower_24}", ''.join(random.choices(string.ascii_lowercase + string.digits, k=24)))
        if "{random_mixed_36}" in pattern:
            pattern = pattern.replace("{random_mixed_36}", ''.join(random.choices(string.ascii_letters + string.digits, k=36)))
        if "{random_mixed_24}" in pattern:
            pattern = pattern.replace("{random_mixed_24}", ''.join(random.choices(string.ascii_letters + string.digits, k=24)))
        if "{random_numbers_12}" in pattern:
            pattern = pattern.replace("{random_numbers_12}", ''.join(random.choices(string.digits, k=12)))
        if "{random_lower_32}" in pattern:
            pattern = pattern.replace("{random_lower_32}", ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)))
        if "secret_key_40" in pattern:
            pattern = pattern.replace("secret_key_40", ''.join(random.choices(string.ascii_letters + string.digits + "+/", k=40)))
        if "secret_32" in pattern:
            pattern = pattern.replace("secret_32", ''.join(random.choices(string.ascii_letters + string.digits, k=32)))
        
        return pattern
    
    def _generate_base64_string(self, length: int) -> str:
        """Generate base64-like string of specified length"""
        chars = string.ascii_letters + string.digits + "+/"
        return ''.join(random.choices(chars, k=length))
    
    async def trigger_token(self, token_id: str, trigger_context: Dict[str, Any]) -> bool:
        """Mark a token as triggered and log the event"""
        if token_id in self.active_tokens:
            token = self.active_tokens[token_id]
            token["accessed"] = True
            token["triggered_at"] = datetime.now(timezone.utc).isoformat()
            token["trigger_context"] = trigger_context
            
            self.triggered_tokens.append(token.copy())
            
            logger.critical(f"HONEYTOKEN TRIGGERED: {token_id} by {trigger_context.get('source_ip', 'unknown')}")
            
            return True
        
        return False
    
    async def get_active_tokens(self) -> List[Dict[str, Any]]:
        """Get list of all active honeytokens"""
        return list(self.active_tokens.values())
    
    async def get_triggered_tokens(self) -> List[Dict[str, Any]]:
        """Get list of all triggered honeytokens"""
        return self.triggered_tokens
    
    async def cleanup_expired_tokens(self, max_age_days: int = 30):
        """Remove old honeytokens"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        expired_tokens = []
        for token_id, token in self.active_tokens.items():
            created_at = datetime.fromisoformat(token["created_at"])
            if created_at < cutoff_date:
                expired_tokens.append(token_id)
        
        for token_id in expired_tokens:
            del self.active_tokens[token_id]
        
        logger.info(f"Cleaned up {len(expired_tokens)} expired honeytokens")
        
        return len(expired_tokens)
