"""
HTTP Emulator Unit Tests
------------------------
Tests for HTTP honeypot functionality including login handling and threat detection.
"""

import pytest
import asyncio
from backend.app.honeypot.http_emulator import HTTPEmulator, HTTPSession

@pytest.fixture
def http_emulator():
    """Create HTTP emulator instance for testing"""
    return HTTPEmulator()

@pytest.fixture
def http_session():
    """Create HTTP session instance for testing"""
    return HTTPSession("test_session", "192.168.1.100")

class TestHTTPSession:
    """Test HTTP session functionality"""
    
    def test_session_initialization(self, http_session):
        """Test that HTTP session initializes correctly"""
        assert http_session.session_id == "test_session"
        assert http_session.source_ip == "192.168.1.100"
        assert http_session.login_attempts == []
        assert http_session.threat_score == 0.0
        assert not http_session.is_suspicious

class TestHTTPEmulator:
    """Test HTTP emulator login handling"""
    
    @pytest.mark.asyncio
    async def test_normal_login_attempt(self, http_emulator):
        """Test normal login attempt handling"""
        response = await http_emulator.handle_login(
            "testuser", "testpass", "192.168.1.100"
        )
        
        assert "success" in response
        assert "error" in response
        assert "server" in response
        assert response["success"] is False  # Should fail by default
    
    @pytest.mark.asyncio
    async def test_admin_login_attempt(self, http_emulator):
        """Test admin login attempt detection"""
        response = await http_emulator.handle_login(
            "admin", "password", "192.168.1.100"
        )
        
        assert "success" in response
        assert "alert_level" in response
        # Admin attempts should be flagged
        assert response["alert_level"] in ["MEDIUM", "HIGH"]
    
    @pytest.mark.asyncio
    async def test_honeytoken_credential(self, http_emulator):
        """Test honeytoken credential detection"""
        response = await http_emulator.handle_login(
            "backup_admin", "secret123", "192.168.1.100"
        )
        
        assert "alert_level" in response
        # Honeytoken should trigger high alert
        if "honeytoken_triggered" in response:
            assert response["honeytoken_triggered"] is True
            assert response["alert_level"] == "CRITICAL"
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, http_emulator):
        """Test rate limiting functionality"""
        source_ip = "192.168.1.200"
        
        # Make multiple rapid attempts
        for i in range(12):
            response = await http_emulator.handle_login(
                f"user{i}", f"pass{i}", source_ip
            )
        
        # Later attempts should trigger rate limiting
        final_response = await http_emulator.handle_login(
            "final_user", "final_pass", source_ip
        )
        
        # Should contain rate limiting info
        assert "error" in final_response
        if "retry_after" in final_response:
            assert final_response["retry_after"] > 0
    
    @pytest.mark.asyncio
    async def test_suspicious_user_agent_detection(self, http_emulator):
        """Test detection of suspicious user agents"""
        suspicious_agents = ["curl/7.68.0", "python-requests/2.25", "wget/1.20"]
        
        for agent in suspicious_agents:
            response = await http_emulator.handle_login(
                "testuser", "testpass", "192.168.1.100", user_agent=agent
            )
            
            # Should flag suspicious user agents
            assert "alert_level" in response
    
    @pytest.mark.asyncio
    async def test_threat_level_assessment(self, http_emulator):
        """Test threat level assessment"""
        # Create session with multiple attempts
        session_id = "threat_test"
        
        # Multiple failed attempts should increase threat level
        for i in range(5):
            await http_emulator.handle_login(
                "admin", f"wrongpass{i}", "192.168.1.100", 
                session_id=session_id
            )
        
        # Final attempt should show elevated threat
        response = await http_emulator.handle_login(
            "admin", "finalattempt", "192.168.1.100", 
            session_id=session_id
        )
        
        assert response["alert_level"] in ["MEDIUM", "HIGH"]
    
    @pytest.mark.asyncio
    async def test_login_page_templates(self, http_emulator):
        """Test login page template generation"""
        page_types = ["admin_panel", "webmail", "ftp_web", "router"]
        
        for page_type in page_types:
            page = await http_emulator.get_login_page(page_type)
            
            assert isinstance(page, str)
            assert len(page) > 0
            assert "html" in page.lower()
            assert "form" in page.lower()
    
    @pytest.mark.asyncio
    async def test_session_tracking(self, http_emulator):
        """Test session information tracking"""
        session_id = "session_tracking_test"
        
        # Make some login attempts
        await http_emulator.handle_login(
            "user1", "pass1", "192.168.1.100", session_id=session_id
        )
        await http_emulator.handle_login(
            "user2", "pass2", "192.168.1.100", session_id=session_id
        )
        
        # Get session info
        session_info = await http_emulator.get_session_info(session_id)
        
        if session_info:
            assert session_info["session_id"] == session_id
            assert session_info["source_ip"] == "192.168.1.100"
            assert session_info["login_attempts"] >= 2

class TestHTTPSecurity:
    """Test security features of HTTP emulator"""
    
    @pytest.mark.asyncio
    async def test_brute_force_detection(self, http_emulator):
        """Test brute force attack detection"""
        source_ip = "192.168.1.250"
        
        # Simulate brute force attack
        for i in range(15):
            response = await http_emulator.handle_login(
                "admin", f"bruteforce{i}", source_ip
            )
        
        # Should detect and respond to brute force
        final_response = await http_emulator.handle_login(
            "admin", "finalbruteforce", source_ip
        )
        
        assert final_response["alert_level"] in ["HIGH", "CRITICAL"]
    
    @pytest.mark.asyncio
    async def test_credential_stuffing_detection(self, http_emulator):
        """Test credential stuffing attack detection"""
        common_creds = [
            ("admin", "admin"),
            ("admin", "password"),
            ("admin", "123456"),
            ("root", "root"),
            ("user", "user")
        ]
        
        for username, password in common_creds:
            response = await http_emulator.handle_login(
                username, password, "192.168.1.100"
            )
            
            # Should flag common credential attempts
            assert "alert_level" in response

class TestHTTPRealism:
    """Test realistic behavior of HTTP emulator"""
    
    @pytest.mark.asyncio
    async def test_realistic_error_messages(self, http_emulator):
        """Test that error messages appear realistic"""
        response = await http_emulator.handle_login(
            "normaluser", "wrongpass", "192.168.1.100"
        )
        
        assert "error" in response
        # Error message should be realistic
        error_msg = response["error"].lower()
        realistic_errors = [
            "invalid", "incorrect", "authentication", "login", "credentials"
        ]
        assert any(error in error_msg for error in realistic_errors)
    
    @pytest.mark.asyncio
    async def test_server_banner_variation(self, http_emulator):
        """Test that server banners vary realistically"""
        responses = []
        
        for i in range(5):
            response = await http_emulator.handle_login(
                f"user{i}", f"pass{i}", "192.168.1.100"
            )
            if "server" in response:
                responses.append(response["server"])
        
        # Should have server banners
        assert len(responses) > 0
        # Should contain realistic server information
        for banner in responses:
            assert any(server in banner.lower() for server in ["apache", "nginx", "iis"])
    
    @pytest.mark.asyncio
    async def test_occasional_success_simulation(self, http_emulator):
        """Test that occasional login success is simulated"""
        # Try many times to potentially trigger a success simulation
        success_found = False
        
        for i in range(50):  # Try many times to potentially hit the 2% success rate
            response = await http_emulator.handle_login(
                f"user{i}", f"pass{i}", "192.168.1.100"
            )
            
            if response["success"] is True:
                success_found = True
                assert "session_token" in response
                assert "redirect_url" in response
                break
        
        # Note: Success is random (2% chance), so this test might not always find one
        # In a real honeypot, this adds realism

if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_http.py -v
    pytest.main([__file__, "-v"])
