"""
SSH Honeypot Server
Accepts SSH connections and provides a FUSE-backed shell environment
"""
import os
import sys
import socket
import threading
import paramiko
from paramiko import ServerInterface
from paramiko.common import AUTH_SUCCESSFUL, OPEN_SUCCEEDED, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
import logging
from io import StringIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SSHServer(paramiko.ServerInterface):
    """SSH Server Interface for Honeypot"""
    
    def __init__(self, audit_callback=None):
        self.event = threading.Event()
        self.audit_callback = audit_callback
        
    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return OPEN_SUCCEEDED
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        
    def check_auth_password(self, username, password):
        """Accept any credentials (honeypot behavior)"""
        if self.audit_callback:
            self.audit_callback("ssh_login", {
                "username": username,
                "password": password,
                "method": "password"
            })
        logger.info(f"[SSH] Login attempt: {username}:{password}")
        return AUTH_SUCCESSFUL
        
    def check_auth_publickey(self, username, key):
        """Accept any public key"""
        if self.audit_callback:
            self.audit_callback("ssh_login", {
                "username": username,
                "key_type": key.get_name(),
                "method": "publickey"
            })
        logger.info(f"[SSH] Key auth: {username}")
        return AUTH_SUCCESSFUL
        
    def get_allowed_auths(self, username):
        return "password,publickey"
        
    def check_channel_shell_request(self, channel):
        self.event.set()
        return True
        
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True
        
    def check_channel_exec_request(self, channel, command):
        """Log command execution attempts"""
        if self.audit_callback:
            self.audit_callback("ssh_exec", {"command": command.decode('utf-8')})
        logger.info(f"[SSH] Exec: {command}")
        return True


class SSHHoneypot:
    """Main SSH Honeypot Server"""
    
    def __init__(self, host="0.0.0.0", port=2222, hostkey_path=None):
        self.host = host
        self.port = port
        self.hostkey_path = hostkey_path or self._generate_hostkey()
        self.running = False
        
    def _generate_hostkey(self):
        """Generate or load SSH host key"""
        key_path = "/tmp/chronos_ssh_host_key"
        if not os.path.exists(key_path):
            logger.info("[SSH] Generating host key...")
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(key_path)
        return key_path
        
    def audit_log(self, event_type, data):
        """Audit logging callback"""
        # This would integrate with PostgreSQL audit system
        logger.info(f"[AUDIT] {event_type}: {data}")
        
    def handle_client(self, client_socket, addr):
        """Handle individual SSH client connection"""
        logger.info(f"[SSH] Connection from {addr}")
        
        try:
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(paramiko.RSAKey(filename=self.hostkey_path))
            
            server = SSHServer(audit_callback=self.audit_log)
            transport.start_server(server=server)
            
            channel = transport.accept(20)
            if channel is None:
                logger.warning("[SSH] No channel established")
                return
                
            server.event.wait(10)
            
            if not server.event.is_set():
                logger.warning("[SSH] Client never requested shell")
                return
                
            # Send welcome banner
            channel.send(b"Welcome to Ubuntu 22.04 LTS (GNU/Linux 5.15.0-56-generic x86_64)\r\n\r\n")
            channel.send(b"The programs included with the Ubuntu system are free software;\r\n")
            channel.send(b"the exact distribution terms for each program are described in the\r\n")
            channel.send(b"individual files in /usr/share/doc/*/copyright.\r\n\r\n")
            channel.send(b"root@honeypot:~# ")
            
            # Simple command loop (in production, this would integrate with FUSE)
            command_buffer = ""
            while True:
                data = channel.recv(1024)
                if not data or len(data) == 0:
                    break
                    
                char = data.decode('utf-8', errors='ignore')
                
                if char == '\r' or char == '\n':
                    if command_buffer.strip():
                        self.audit_log("ssh_command", {"command": command_buffer.strip()})
                        logger.info(f"[SSH] Command: {command_buffer.strip()}")
                        
                        # Simple echo for now (would integrate with FUSE shell)
                        response = self._execute_command(command_buffer.strip())
                        channel.send(response.encode() + b"\r\n")
                    
                    command_buffer = ""
                    channel.send(b"root@honeypot:~# ")
                elif char == '\x03':  # Ctrl+C
                    channel.send(b"^C\r\n")
                    command_buffer = ""
                    channel.send(b"root@honeypot:~# ")
                elif char == '\x7f':  # Backspace
                    if command_buffer:
                        command_buffer = command_buffer[:-1]
                        channel.send(b"\b \b")
                else:
                    command_buffer += char
                    channel.send(data)
                    
        except Exception as e:
            logger.error(f"[SSH] Error: {e}")
        finally:
            try:
                transport.close()
            except:
                pass
            client_socket.close()
            logger.info(f"[SSH] Connection closed: {addr}")
            
    def _execute_command(self, command):
        """Execute command (stub - would integrate with FUSE)"""
        # In production, this would route through the FUSE filesystem
        if command.startswith("ls"):
            return "bin  boot  dev  etc  home  lib  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var"
        elif command.startswith("pwd"):
            return "/root"
        elif command.startswith("whoami"):
            return "root"
        elif command.startswith("uname"):
            return "Linux honeypot 5.15.0-56-generic #62-Ubuntu SMP x86_64 GNU/Linux"
        else:
            return f"-bash: {command.split()[0]}: command not found"
            
    def start(self):
        """Start the SSH honeypot server"""
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(100)
        
        logger.info(f"[SSH] Honeypot listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            logger.info("[SSH] Shutting down...")
        finally:
            server_socket.close()
            
    def stop(self):
        """Stop the server"""
        self.running = False


if __name__ == "__main__":
    honeypot = SSHHoneypot(port=2222)
    honeypot.start()
