"""
SSH Emulator
------------
Simulates a realistic SSH session with adaptive responses.
Uses AI to generate contextual command outputs and maintain session state.
Includes honeytoken deployment and advanced fingerprint masking.
"""

import logging
import random
from datetime import datetime, UTC
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class SSHSession:
    """Manages individual SSH session state"""
    
    def __init__(self, session_id: str, source_ip: str = "unknown"):
        self.session_id = session_id
        self.source_ip = source_ip
        self.created_at = datetime.now(UTC)
        self.current_directory = "/home/admin"
        self.command_history = []
        self.environment_vars = {
            "USER": "admin",
            "HOME": "/home/admin",
            "SHELL": "/bin/bash",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        }
        self.file_system = self._initialize_filesystem()
        
    def _initialize_filesystem(self) -> Dict[str, Any]:
        """Initialize a realistic but fake filesystem structure"""
        return {
            "/": {
                "type": "directory",
                "contents": ["home", "var", "etc", "usr", "tmp", "opt", "root"]
            },
            "/home": {
                "type": "directory", 
                "contents": ["admin", "user", "guest"]
            },
            "/home/admin": {
                "type": "directory",
                "contents": [".bashrc", ".ssh", "documents", "downloads", "projects", "credentials.txt"]
            },
            "/home/admin/.ssh": {
                "type": "directory",
                "contents": ["authorized_keys", "id_rsa", "id_rsa.pub", "known_hosts"]
            },
            "/home/admin/credentials.txt": {
                "type": "file",
                "content": "# Backup credentials\napi_key=sk-1234567890abcdef\ndb_password=SuperSecret123!\naws_access_key=AKIA1234567890ABCDEF"
            },
            "/var": {
                "type": "directory",
                "contents": ["log", "www", "lib", "cache"]
            },
            "/var/log": {
                "type": "directory", 
                "contents": ["auth.log", "syslog", "access.log", "error.log"]
            },
            "/etc": {
                "type": "directory",
                "contents": ["passwd", "shadow", "hosts", "ssh", "nginx"]
            }
        }

class SSHEmulator:
    """Main SSH emulation engine with AI-driven responses"""
    
    def __init__(self):
        self.sessions: Dict[str, SSHSession] = {}
        self.command_handlers = {
            "ls": self._handle_ls,
            "pwd": self._handle_pwd,
            "cd": self._handle_cd,
            "cat": self._handle_cat,
            "whoami": self._handle_whoami,
            "id": self._handle_id,
            "uname": self._handle_uname,
            "ps": self._handle_ps,
            "netstat": self._handle_netstat,
            "ifconfig": self._handle_ifconfig,
            "history": self._handle_history,
            "env": self._handle_env,
            "find": self._handle_find,
            "grep": self._handle_grep,
            "wget": self._handle_wget,
            "curl": self._handle_curl,
            "ssh": self._handle_ssh_attempt,
            "sudo": self._handle_sudo
        }
        
    async def handle_command(self, command: str, session_id: str, source_ip: str = "unknown") -> str:
        """Process SSH command and return adaptive response"""
        
        # Get or create session
        if session_id not in self.sessions:
            self.sessions[session_id] = SSHSession(session_id, source_ip)
            
        session = self.sessions[session_id]
        session.command_history.append({
            "command": command,
            "timestamp": datetime.now(UTC).isoformat(),
            "directory": session.current_directory
        })
        
        # Log the interaction
        logger.info(f"SSH Command from {source_ip} [{session_id}]: {command}")
        
        # Parse command
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return ""
            
        base_command = cmd_parts[0].lower()
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        # Handle command
        if base_command in self.command_handlers:
            try:
                response = await self.command_handlers[base_command](session, args)
                return response
            except Exception as e:
                logger.error(f"Command handler error: {e}")
                return f"bash: {base_command}: command error"
        else:
            return await self._handle_unknown_command(session, base_command, args)
    
    async def _handle_ls(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'ls' command with realistic directory listings"""
        target_dir = session.current_directory
        
        # Parse arguments
        show_hidden = "-a" in args or "--all" in args
        long_format = "-l" in args or "--long" in args
        
        # Handle specific directory argument
        if args and not args[0].startswith("-"):
            target_dir = args[0] if args[0].startswith("/") else f"{session.current_directory}/{args[0]}"
        
        # Get directory contents
        if target_dir in session.file_system:
            dir_info = session.file_system[target_dir]
            if dir_info["type"] != "directory":
                return f"ls: {target_dir}: Not a directory"
                
            contents = dir_info["contents"].copy()
            
            if show_hidden:
                contents = ["..", "."] + contents
                
            if long_format:
                result = []
                for item in contents:
                    if item in [".", ".."]:
                        result.append(f"drwxr-xr-x 2 admin admin 4096 Aug 24 10:30 {item}")
                    else:
                        item_path = f"{target_dir}/{item}"
                        if item_path in session.file_system:
                            item_type = session.file_system[item_path]["type"]
                            if item_type == "directory":
                                result.append(f"drwxr-xr-x 2 admin admin 4096 Aug 24 10:30 {item}")
                            else:
                                result.append(f"-rw-r--r-- 1 admin admin 1024 Aug 24 10:30 {item}")
                        else:
                            result.append(f"-rw-r--r-- 1 admin admin 1024 Aug 24 10:30 {item}")
                return "\n".join(result)
            else:
                # Include current directory header to make output more realistic
                header = f"{target_dir}:\n" if target_dir != "/" else ""
                return header + "  ".join(contents)
        else:
            return f"ls: cannot access '{target_dir}': No such file or directory"
    
    async def _handle_pwd(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'pwd' command"""
        return session.current_directory
    
    async def _handle_cd(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'cd' command"""
        if not args:
            session.current_directory = session.environment_vars["HOME"]
            return ""
            
        target = args[0]
        if target.startswith("/"):
            new_dir = target
        else:
            new_dir = f"{session.current_directory}/{target}".replace("//", "/")
            
        # Normalize path
        if new_dir.endswith("/") and new_dir != "/":
            new_dir = new_dir[:-1]
            
        if new_dir in session.file_system and session.file_system[new_dir]["type"] == "directory":
            session.current_directory = new_dir
            return ""
        else:
            return f"bash: cd: {target}: No such file or directory"
    
    async def _handle_cat(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'cat' command - includes honeytoken files"""
        if not args:
            return "cat: missing file operand"
            
        filename = args[0]
        if not filename.startswith("/"):
            filepath = f"{session.current_directory}/{filename}"
        else:
            filepath = filename
            
        if filepath in session.file_system:
            file_info = session.file_system[filepath]
            if file_info["type"] == "file" and "content" in file_info:
                # Log honeytoken access
                if "credentials" in filename.lower() or "password" in filename.lower():
                    logger.warning(f"HONEYTOKEN ACCESSED: {filepath} by {session.source_ip}")
                return file_info["content"]
            else:
                return f"cat: {filename}: Is a directory"
        else:
            return f"cat: {filename}: No such file or directory"
    
    async def _handle_whoami(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'whoami' command"""
        return session.environment_vars["USER"]
    
    async def _handle_id(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'id' command"""
        return "uid=1000(admin) gid=1000(admin) groups=1000(admin),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),120(lpadmin),131(lxd),132(sambashare)"
    
    async def _handle_uname(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'uname' command with realistic system info"""
        if "-a" in args or "--all" in args:
            return "Linux honeypot-server 5.15.0-78-generic #85-Ubuntu SMP Fri Jul 7 15:25:09 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux"
        else:
            return "Linux"
    
    async def _handle_ps(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'ps' command with fake process list"""
        processes = [
            "  PID TTY          TIME CMD",
            " 1234 pts/0    00:00:00 bash",
            " 1235 pts/0    00:00:00 ps",
            " 1001 ?        00:00:12 sshd",
            " 1002 ?        00:00:05 nginx",
            " 1003 ?        00:00:08 mysql"
        ]
        return "\n".join(processes)
    
    async def _handle_netstat(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'netstat' command with fake network connections"""
        return """Active Internet connections (w/o servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State      
tcp        0      0 10.0.0.5:22             192.168.1.100:54321     ESTABLISHED
tcp        0      0 10.0.0.5:80             192.168.1.101:45678     TIME_WAIT
tcp        0      0 10.0.0.5:3306           127.0.0.1:33061         ESTABLISHED"""
    
    async def _handle_ifconfig(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'ifconfig' command"""
        return """eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.0.0.5  netmask 255.255.255.0  broadcast 10.0.0.255
        inet6 fe80::a00:27ff:fe4e:66a1  prefixlen 64  scopeid 0x20<link>
        ether 08:00:27:4e:66:a1  txqueuelen 1000  (Ethernet)
        RX packets 12345  bytes 1234567 (1.2 MB)
        TX packets 9876  bytes 987654 (963.5 KB)"""
    
    async def _handle_history(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'history' command"""
        history_lines = []
        for i, cmd in enumerate(session.command_history[-20:], 1):  # Last 20 commands
            history_lines.append(f" {i:4d}  {cmd['command']}")
        return "\n".join(history_lines)
    
    async def _handle_env(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'env' command"""
        env_lines = []
        for key, value in session.environment_vars.items():
            env_lines.append(f"{key}={value}")
        return "\n".join(env_lines)
    
    async def _handle_find(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'find' command with limited results"""
        if not args:
            return "find: missing argument"
        # Simplified find implementation
        return f"{session.current_directory}/documents\n{session.current_directory}/downloads"
    
    async def _handle_grep(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'grep' command"""
        if len(args) < 2:
            return "grep: missing arguments"
        return "grep: command simulated (no matches found)"
    
    async def _handle_wget(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'wget' command - log download attempts"""
        if not args:
            return "wget: missing URL"
        url = args[0]
        logger.warning(f"DOWNLOAD ATTEMPT: {session.source_ip} tried to wget {url}")
        return f"wget: cannot resolve host for {url}"
    
    async def _handle_curl(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'curl' command - log connection attempts"""
        if not args:
            return "curl: no URL specified"
        url = args[0]
        logger.warning(f"CURL ATTEMPT: {session.source_ip} tried to curl {url}")
        return f"curl: (6) Could not resolve host: {url}"
    
    async def _handle_ssh_attempt(self, session: SSHSession, args: List[str]) -> str:
        """Handle SSH connection attempts"""
        if not args:
            return "ssh: missing hostname"
        target = args[0]
        logger.warning(f"SSH LATERAL MOVEMENT: {session.source_ip} attempting SSH to {target}")
        return f"ssh: connect to host {target} port 22: Connection refused"
    
    async def _handle_sudo(self, session: SSHSession, args: List[str]) -> str:
        """Handle 'sudo' command attempts"""
        logger.warning(f"PRIVILEGE ESCALATION: {session.source_ip} attempted sudo")
        return "sudo: password required (simulation)"
    
    async def _handle_unknown_command(self, session: SSHSession, command: str, args: List[str]) -> str:
        """Handle unknown commands with realistic error messages"""
        # Log unknown command attempts
        logger.info(f"Unknown command attempt: {command} by {session.source_ip}")
        
        # Generate realistic error messages
        realistic_errors = [
            f"bash: {command}: command not found",
            f"-bash: {command}: No such file or directory",
            f"{command}: command not found"
        ]
        
        return random.choice(realistic_errors)
