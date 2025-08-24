"""
Configuration Management
------------------------
Centralized configuration for all Mirage honeypot components.
Supports environment variables, configuration files, and runtime settings.
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = "localhost"
    port: int = 5432
    name: str = "mirage_honeypot"
    user: str = "mirage"
    password: str = "changeme"
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

@dataclass
class AIConfig:
    """AI engine configuration"""
    provider: str = "openai"  # openai, anthropic, local
    api_key: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 500
    temperature: float = 0.7
    enable_adaptive_responses: bool = True
    response_cache_ttl: int = 3600  # seconds

@dataclass
class HoneypotConfig:
    """Honeypot service configuration"""
    ssh_port: int = 2222
    http_port: int = 8080
    tcp_port: int = 9999
    iot_port: int = 8081
    
    # SSH emulator settings
    ssh_welcome_banner: str = "Ubuntu 20.04.3 LTS"
    ssh_motd: str = "Welcome to production server"
    ssh_fake_users: Optional[List[str]] = None
    
    # HTTP emulator settings
    http_fake_apps: Optional[List[str]] = None
    http_login_paths: Optional[List[str]] = None
    
    # Rate limiting
    max_attempts_per_ip: int = 100
    rate_limit_window: int = 3600  # seconds
    
    def __post_init__(self):
        if self.ssh_fake_users is None:
            self.ssh_fake_users = ["admin", "root", "user", "ubuntu", "postgres", "mysql"]
        
        if self.http_fake_apps is None:
            self.http_fake_apps = ["wordpress", "phpmyadmin", "jenkins", "grafana"]
        
        if self.http_login_paths is None:
            self.http_login_paths = ["/admin", "/login", "/wp-admin", "/dashboard"]

@dataclass
class HoneytokenConfig:
    """Honeytoken configuration"""
    default_expiry_days: int = 30
    callback_url: str = "http://localhost:8000/api/v1/honeytokens/callback"
    enable_web_beacons: bool = True
    fake_api_providers: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.fake_api_providers is None:
            self.fake_api_providers = ["openai", "stripe", "aws", "github", "slack"]

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: str = "10MB"
    backup_count: int = 5
    enable_json_logs: bool = False

@dataclass
class SecurityConfig:
    """Security and privacy settings"""
    enable_ip_anonymization: bool = True
    anonymization_salt: str = "mirage_default_salt"
    enable_data_retention_limits: bool = True
    data_retention_days: int = 90
    enable_encryption_at_rest: bool = False
    encryption_key: Optional[str] = None

class Config:
    """Main configuration class that loads and manages all settings"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv("MIRAGE_CONFIG", "config.json")
        
        # Initialize with defaults
        self.database = DatabaseConfig()
        self.ai = AIConfig()
        self.honeypot = HoneypotConfig()
        self.honeytokens = HoneytokenConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
        
        # Load configuration
        self._load_from_env()
        self._load_from_file()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Database settings
        db_host = os.getenv("DB_HOST")
        if db_host:
            self.database.host = db_host
        db_port = os.getenv("DB_PORT")
        if db_port:
            self.database.port = int(db_port)
        db_name = os.getenv("DB_NAME")
        if db_name:
            self.database.name = db_name
        db_user = os.getenv("DB_USER")
        if db_user:
            self.database.user = db_user
        db_password = os.getenv("DB_PASSWORD")
        if db_password:
            self.database.password = db_password
        
        # AI settings
        ai_provider = os.getenv("AI_PROVIDER")
        if ai_provider:
            self.ai.provider = ai_provider
        if os.getenv("AI_API_KEY"):
            self.ai.api_key = os.getenv("AI_API_KEY")
        ai_model = os.getenv("AI_MODEL")
        if ai_model:
            self.ai.model = ai_model
        
        # Honeypot ports
        ssh_port = os.getenv("SSH_PORT")
        if ssh_port:
            self.honeypot.ssh_port = int(ssh_port)
        http_port = os.getenv("HTTP_PORT")
        if http_port:
            self.honeypot.http_port = int(http_port)
        tcp_port = os.getenv("TCP_PORT")
        if tcp_port:
            self.honeypot.tcp_port = int(tcp_port)
        iot_port = os.getenv("IOT_PORT")
        if iot_port:
            self.honeypot.iot_port = int(iot_port)
        
        # Logging
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            self.logging.level = log_level
        if os.getenv("LOG_FILE"):
            self.logging.file_path = os.getenv("LOG_FILE")
    
    def _load_from_file(self):
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            return
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Update configuration sections
            if 'database' in config_data:
                for key, value in config_data['database'].items():
                    if hasattr(self.database, key):
                        setattr(self.database, key, value)
            
            if 'ai' in config_data:
                for key, value in config_data['ai'].items():
                    if hasattr(self.ai, key):
                        setattr(self.ai, key, value)
            
            if 'honeypot' in config_data:
                for key, value in config_data['honeypot'].items():
                    if hasattr(self.honeypot, key):
                        setattr(self.honeypot, key, value)
            
            if 'honeytokens' in config_data:
                for key, value in config_data['honeytokens'].items():
                    if hasattr(self.honeytokens, key):
                        setattr(self.honeytokens, key, value)
            
            if 'logging' in config_data:
                for key, value in config_data['logging'].items():
                    if hasattr(self.logging, key):
                        setattr(self.logging, key, value)
            
            if 'security' in config_data:
                for key, value in config_data['security'].items():
                    if hasattr(self.security, key):
                        setattr(self.security, key, value)
        
        except Exception as e:
            print(f"Warning: Failed to load config file {self.config_file}: {e}")
    
    def save_to_file(self, file_path: Optional[str] = None):
        """Save current configuration to file"""
        output_file = file_path or self.config_file
        
        config_data = {
            'database': {
                'host': self.database.host,
                'port': self.database.port,
                'name': self.database.name,
                'user': self.database.user,
                # Don't save password to file
            },
            'ai': {
                'provider': self.ai.provider,
                'model': self.ai.model,
                'max_tokens': self.ai.max_tokens,
                'temperature': self.ai.temperature,
                'enable_adaptive_responses': self.ai.enable_adaptive_responses,
                'response_cache_ttl': self.ai.response_cache_ttl
            },
            'honeypot': {
                'ssh_port': self.honeypot.ssh_port,
                'http_port': self.honeypot.http_port,
                'tcp_port': self.honeypot.tcp_port,
                'iot_port': self.honeypot.iot_port,
                'ssh_welcome_banner': self.honeypot.ssh_welcome_banner,
                'ssh_motd': self.honeypot.ssh_motd,
                'ssh_fake_users': self.honeypot.ssh_fake_users,
                'http_fake_apps': self.honeypot.http_fake_apps,
                'http_login_paths': self.honeypot.http_login_paths,
                'max_attempts_per_ip': self.honeypot.max_attempts_per_ip,
                'rate_limit_window': self.honeypot.rate_limit_window
            },
            'honeytokens': {
                'default_expiry_days': self.honeytokens.default_expiry_days,
                'callback_url': self.honeytokens.callback_url,
                'enable_web_beacons': self.honeytokens.enable_web_beacons,
                'fake_api_providers': self.honeytokens.fake_api_providers
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'file_path': self.logging.file_path,
                'max_file_size': self.logging.max_file_size,
                'backup_count': self.logging.backup_count,
                'enable_json_logs': self.logging.enable_json_logs
            },
            'security': {
                'enable_ip_anonymization': self.security.enable_ip_anonymization,
                'enable_data_retention_limits': self.security.enable_data_retention_limits,
                'data_retention_days': self.security.data_retention_days,
                'enable_encryption_at_rest': self.security.enable_encryption_at_rest
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save config to {output_file}: {e}")
    
    def get_section(self, section_name: str) -> Any:
        """Get a configuration section by name"""
        sections = {
            'database': self.database,
            'ai': self.ai,
            'honeypot': self.honeypot,
            'honeytokens': self.honeytokens,
            'logging': self.logging,
            'security': self.security
        }
        return sections.get(section_name)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Validate AI config
        if self.ai.provider in ['openai', 'anthropic'] and not self.ai.api_key:
            issues.append("AI API key is required for external providers")
        
        # Validate ports
        if not (1024 <= self.honeypot.ssh_port <= 65535):
            issues.append("SSH port must be between 1024 and 65535")
        if not (1024 <= self.honeypot.http_port <= 65535):
            issues.append("HTTP port must be between 1024 and 65535")
        if not (1024 <= self.honeypot.tcp_port <= 65535):
            issues.append("TCP port must be between 1024 and 65535")
        if not (1024 <= self.honeypot.iot_port <= 65535):
            issues.append("IoT port must be between 1024 and 65535")
        
        # Check for port conflicts
        ports = [self.honeypot.ssh_port, self.honeypot.http_port, 
                self.honeypot.tcp_port, self.honeypot.iot_port]
        if len(ports) != len(set(ports)):
            issues.append("Port conflicts detected - all ports must be unique")
        
        # Validate data retention
        if self.security.data_retention_days < 1:
            issues.append("Data retention days must be at least 1")
        
        return issues

# Global configuration instance
config = Config()

# Convenience functions
def get_config() -> Config:
    """Get the global configuration instance"""
    return config

def reload_config():
    """Reload configuration from files and environment"""
    global config
    config = Config(config.config_file)
