"""
SSH Honeypot Server
Accepts SSH connections and provides a FUSE-backed shell environment.

Phase 2 addition: session_id is generated per-connection and injected into
fuse_context (threading.local) before every FUSE-touching operation.
This makes every read()/write()/open() session-aware without /proc lookups.
"""
import os
import sys
import socket
import threading
import uuid
import paramiko
from paramiko import ServerInterface
from paramiko.common import AUTH_SUCCESSFUL, OPEN_SUCCEEDED, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
import logging
from io import StringIO

from chronos.interface.fuse import fuse_context
from chronos.gateway.shell_parser import ShellParser, ParserError
from chronos.gateway.dispatcher import SessionEnvironment, ASTDispatcher
import time

try:
    from chronos.intelligence.ubuntu_profile import UbuntuProfile as _UbuntuProfile
    _profile = _UbuntuProfile()
except Exception:
    _profile = None

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
    
    def __init__(self, host="0.0.0.0", port=2222, hostkey_path=None, db_layer=None):
        self.host = host
        self.port = port
        self.hostkey_path = hostkey_path or self._generate_hostkey()
        self.db_layer = db_layer
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
        logger.info(f"[AUDIT] {event_type}: {data}")
        session_id = data.get("session_id", getattr(fuse_context, "session_id", None))
        if self.db_layer and session_id:
            self.db_layer.log_operation(session_id, event_type, "", 0, data)
        
    def handle_client(self, client_socket, addr):
        """Handle individual SSH client connection."""
        logger.info(f"[SSH] Connection from {addr}")

        # Generate a unique session identity for this connection.
        # This is injected into fuse_context so every FUSE syscall knows which
        # session it belongs to — no /proc lookups, no PID heuristics.
        session_id = str(uuid.uuid4())
        fuse_context.session_id = session_id
        logger.info(f"[SSH] Session assigned: {session_id} from {addr}")
        
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
                
            # Send welcome banner derived from the Ubuntu profile
            ubuntu_version = _profile.ubuntu_version if _profile else "24.04"
            kernel_version = _profile.kernel_version if _profile else "6.8.0-51-generic"
            hostname = _profile.hostname if _profile else "ubuntu"
            primary_user = _profile.primary_user if _profile else "ubuntu"

            channel.send(f"Welcome to Ubuntu {ubuntu_version} LTS (GNU/Linux {kernel_version} x86_64)\r\n\r\n".encode())
            channel.send(b"The programs included with the Ubuntu system are free software;\r\n")
            channel.send(b"the exact distribution terms for each program are described in the\r\n")
            channel.send(b"individual files in /usr/share/doc/*/copyright.\r\n\r\n")
            channel.send(f"{primary_user}@{hostname}:~$ ".encode())
            
            # Simple command loop
            command_buffer = ""
            
            env = SessionEnvironment(username=primary_user)
            parser = ShellParser()
            dispatcher = ASTDispatcher(env)
            
            while True:
                data = channel.recv(1024)
                if not data or len(data) == 0:
                    break
                    
                char = data.decode('utf-8', errors='ignore')
                
                if char == "\r" or char == "\n":
                    channel.send(b"\r\n")
                    if command_buffer.strip():
                        # Set session context before any potential FUSE operations
                        fuse_context.session_id = session_id
                        self.audit_log("ssh_command", {
                            "command": command_buffer.strip(),
                            "session_id": session_id,
                        })
                        logger.info(f"[SSH] [{session_id[:8]}] Command: {command_buffer.strip()}")
                        
                        try:
                            # We import world_simulation here to avoid circular imports 
                            # if it's imported at the top level
                            from chronos.simulation.orchestrator import world_simulation
                            from chronos.simulation.event_bus import CommandStarted, CommandSucceeded, CommandFailed, CommandParsed
                            
                            ts = time.time()
                            world_simulation.event_bus.publish(CommandStarted(session_id, command_buffer.strip(), ts))
                            
                            sequence = parser.parse(command_buffer.strip())
                            world_simulation.event_bus.publish(CommandParsed(session_id, command_buffer.strip(), time.time()))
                            
                            returncode, response = dispatcher.execute_sequence(sequence)
                            
                            if returncode == 0:
                                world_simulation.event_bus.publish(CommandSucceeded(session_id, command_buffer.strip(), response, time.time()))
                            else:
                                world_simulation.event_bus.publish(CommandFailed(session_id, command_buffer.strip(), response, time.time()))
                                
                        except Exception as e:
                            response = str(e) + "\n"
                            # For parser failures or uncaught errors
                            from chronos.simulation.orchestrator import world_simulation
                            from chronos.simulation.event_bus import CommandFailed
                            world_simulation.event_bus.publish(CommandFailed(session_id, command_buffer.strip(), response, time.time()))
                            
                        if response:
                            if not response.endswith("\n"):
                                response += "\n"
                            channel.send(response.replace("\n", "\r\n").encode())
                    command_buffer = ""
                    prompt_cwd = "~" if env.env["PWD"] == env.env["HOME"] else env.env["PWD"]
                    channel.send(f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode())
                elif char == '\x03':  # Ctrl+C
                    channel.send(b"^C\r\n")
                    command_buffer = ""
                    prompt_cwd = "~" if env.env["PWD"] == env.env["HOME"] else env.env["PWD"]
                    channel.send(f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode())
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
            
            self.audit_log("ssh_disconnect", {
                "session_id": session_id,
            })
            logger.info(f"[SSH] Connection closed: {addr}")
            
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
