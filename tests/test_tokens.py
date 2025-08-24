"""
Honeytoken Tests
---------------
Tests for honeytoken generation and management functionality.
"""

import pytest
import asyncio
from backend.app.honeypot.tokens import HoneytokenGenerator, HoneytokenType

@pytest.fixture
def token_generator():
    """Create honeytoken generator instance for testing"""
    return HoneytokenGenerator()

class TestHoneytokenGeneration:
    """Test honeytoken generation functionality"""
    
    def test_credential_generation(self, token_generator):
        """Test credential honeytoken generation"""
        cred = token_generator.generate_credentials("database")
        
        assert "username" in cred
        assert "password" in cred
        assert "service_type" in cred
        assert "token_id" in cred
        assert cred["service_type"] == "database"
        assert cred["accessed"] is False
        
        # Check realistic patterns
        assert len(cred["username"]) > 0
        assert len(cred["password"]) > 0
    
    def test_api_key_generation(self, token_generator):
        """Test API key honeytoken generation"""
        api_key = token_generator.generate_api_key("openai")
        
        assert "api_key" in api_key
        assert "provider" in api_key
        assert "token_id" in api_key
        assert api_key["provider"] == "openai"
        assert api_key["api_key"].startswith("sk-")
        assert len(api_key["api_key"]) > 10
    
    def test_aws_api_key_generation(self, token_generator):
        """Test AWS API key generation"""
        aws_key = token_generator.generate_api_key("aws")
        
        assert aws_key["provider"] == "aws"
        assert aws_key["api_key"].startswith("AKIA")
        assert len(aws_key["api_key"]) >= 20
    
    def test_ssh_key_generation(self, token_generator):
        """Test SSH key pair generation"""
        ssh_key = token_generator.generate_ssh_key()
        
        assert "private_key" in ssh_key
        assert "public_key" in ssh_key
        assert "token_id" in ssh_key
        assert "BEGIN OPENSSH PRIVATE KEY" in ssh_key["private_key"]
        assert ssh_key["public_key"].startswith("ssh-rsa")
        assert ssh_key["key_type"] == "rsa"
        assert ssh_key["key_size"] == 2048
    
    def test_config_file_generation(self, token_generator):
        """Test configuration file honeytoken generation"""
        config = token_generator.generate_config_file("database")
        
        assert "filename" in config
        assert "content" in config
        assert "config_type" in config
        assert "token_id" in config
        assert config["config_type"] == "database"
        assert config["filename"] == ".env"
        assert "DB_PASSWORD" in config["content"]
    
    def test_web_beacon_generation(self, token_generator):
        """Test web beacon honeytoken generation"""
        beacon = token_generator.generate_web_beacon("http://callback.local")
        
        assert "beacon_id" in beacon
        assert "callback_url" in beacon
        assert "html_beacon" in beacon
        assert "script_beacon" in beacon
        assert beacon["callback_url"] == "http://callback.local"
        assert "<img src=" in beacon["html_beacon"]
        assert "fetch(" in beacon["script_beacon"]

class TestHoneytokenTracking:
    """Test honeytoken tracking and triggering"""
    
    @pytest.mark.asyncio
    async def test_token_triggering(self, token_generator):
        """Test honeytoken triggering mechanism"""
        # Generate a token
        cred = token_generator.generate_credentials("test")
        token_id = cred["token_id"]
        
        # Trigger the token
        trigger_context = {
            "source_ip": "192.168.1.100",
            "access_type": "credential_exposure"
        }
        
        result = await token_generator.trigger_token(token_id, trigger_context)
        
        assert result is True
        
        # Check that token is marked as accessed
        active_tokens = await token_generator.get_active_tokens()
        triggered_token = next((t for t in active_tokens if t["token_id"] == token_id), None)
        assert triggered_token is not None
        assert triggered_token["accessed"] is True
        assert "triggered_at" in triggered_token
    
    @pytest.mark.asyncio
    async def test_triggered_tokens_list(self, token_generator):
        """Test retrieval of triggered tokens"""
        # Generate and trigger a token
        cred = token_generator.generate_credentials("test")
        await token_generator.trigger_token(
            cred["token_id"], 
            {"source_ip": "192.168.1.100"}
        )
        
        triggered_tokens = await token_generator.get_triggered_tokens()
        
        assert len(triggered_tokens) > 0
        assert any(t["token_id"] == cred["token_id"] for t in triggered_tokens)
    
    @pytest.mark.asyncio
    async def test_active_tokens_list(self, token_generator):
        """Test retrieval of active tokens"""
        # Generate multiple tokens
        token_generator.generate_credentials("database")
        token_generator.generate_api_key("openai")
        token_generator.generate_ssh_key()
        
        active_tokens = await token_generator.get_active_tokens()
        
        assert len(active_tokens) >= 3
        assert all("token_id" in token for token in active_tokens)
    
    @pytest.mark.asyncio
    async def test_nonexistent_token_trigger(self, token_generator):
        """Test triggering non-existent token"""
        result = await token_generator.trigger_token(
            "fake_token_id", 
            {"source_ip": "192.168.1.100"}
        )
        
        assert result is False

class TestHoneytokenRealism:
    """Test realism of generated honeytokens"""
    
    def test_realistic_usernames(self, token_generator):
        """Test that generated usernames look realistic"""
        service_types = ["database", "api", "backup", "monitoring"]
        
        for service_type in service_types:
            cred = token_generator.generate_credentials(service_type)
            username = cred["username"]
            
            # Should contain service-related terms
            assert any(term in username.lower() for term in [
                service_type, "admin", "service", "user", "monitor", "backup", "api", "db"
            ])
    
    def test_realistic_passwords(self, token_generator):
        """Test that generated passwords follow realistic patterns"""
        passwords = []
        
        for _ in range(10):
            cred = token_generator.generate_credentials("test")
            passwords.append(cred["password"])
        
        for password in passwords:
            # Should have reasonable length
            assert len(password) >= 8
            # Should contain variety of characters
            assert any(c.isalpha() for c in password)
            assert any(c.isdigit() for c in password)
    
    def test_api_key_format_compliance(self, token_generator):
        """Test that API keys follow proper format conventions"""
        providers = ["openai", "aws", "stripe", "github", "slack"]
        
        for provider in providers:
            api_key = token_generator.generate_api_key(provider)
            key = api_key["api_key"]
            
            if provider == "openai":
                assert key.startswith("sk-")
            elif provider == "aws":
                assert key.startswith("AKIA")
            elif provider == "stripe":
                assert key.startswith("sk_live_")
            elif provider == "github":
                assert key.startswith("ghp_")
            elif provider == "slack":
                assert key.startswith("xoxb-")
    
    def test_config_file_realism(self, token_generator):
        """Test that config files contain realistic content"""
        config_types = ["database", "aws", "docker"]
        
        for config_type in config_types:
            config = token_generator.generate_config_file(config_type)
            content = config["content"]
            
            # Should contain appropriate configuration keys
            if config_type == "database":
                assert "DB_" in content
                assert "PASSWORD" in content
            elif config_type == "aws":
                assert "aws_access_key_id" in content
                assert "aws_secret_access_key" in content
            elif config_type == "docker":
                assert "version:" in content
                assert "services:" in content

class TestHoneytokenSecurity:
    """Test security aspects of honeytoken system"""
    
    def test_unique_token_ids(self, token_generator):
        """Test that generated token IDs are unique"""
        token_ids = set()
        
        for _ in range(20):
            cred = token_generator.generate_credentials("test")
            token_id = cred["token_id"]
            
            # Should not have duplicates
            assert token_id not in token_ids
            token_ids.add(token_id)
    
    def test_token_id_format(self, token_generator):
        """Test token ID format consistency"""
        cred = token_generator.generate_credentials("test")
        token_id = cred["token_id"]
        
        # Should follow expected format
        assert token_id.startswith("ht_")
        assert len(token_id) > 10
        assert "_" in token_id
    
    @pytest.mark.asyncio
    async def test_token_cleanup(self, token_generator):
        """Test token cleanup functionality"""
        # Generate some tokens
        initial_count = len(await token_generator.get_active_tokens())
        
        token_generator.generate_credentials("test")
        token_generator.generate_api_key("test")
        
        new_count = len(await token_generator.get_active_tokens())
        assert new_count > initial_count
        
        # Test cleanup (this would normally clean old tokens)
        cleaned = await token_generator.cleanup_expired_tokens(max_age_days=30)
        assert cleaned >= 0  # Should return number of cleaned tokens

if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_tokens.py -v
    pytest.main([__file__, "-v"])
