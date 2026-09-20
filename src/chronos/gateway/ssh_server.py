"""
SSH Honeypot Server
Accepts SSH connections and provides a FUSE-backed shell environment.

Uses a strict Command Emulator. Each session runs a persistent worker process,
whose PID is mapped to the session_id in Redis. This ensures proper attribution
in the FUSE filesystem via fuse_get_context()[2].
"""

import os
import sys
import socket
import threading
import multiprocessing
import uuid
import paramiko
from paramiko import ServerInterface
from paramiko.common import (
    AUTH_SUCCESSFUL,
    OPEN_SUCCEEDED,
    OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED,
)
import logging
from io import StringIO
import time
import redis
import codecs

try:
    from chronos.intelligence.ubuntu_profile import UbuntuProfile as _UbuntuProfile

    _profile = _UbuntuProfile()
except Exception:
    _profile = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def session_worker(session_id, primary_user, pipe_conn):
    """Runs in a separate process per SSH session. Emulates commands and touches FUSE."""
    pid = os.getpid()
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    # DNS after chroot would read resolver files through the honeypot itself.
    # A worker never survives a Redis connection loss; resolve before containment.
    redis_host = socket.gethostbyname(redis_host)
    r = redis.Redis(
        host=redis_host,
        port=6379,
        db=0,
        decode_responses=True,
        socket_timeout=3,
        socket_connect_timeout=3,
    )

    try:
        from chronos.gateway.containment import is_honeypot_mount
        if not is_honeypot_mount("/mnt/honeypot"):
            raise RuntimeError("Honeypot filesystem is not mounted")
        import resource

        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        # Register PID mapping for FUSE attribution
        r.setex(f"session_pid:{pid}", 120, session_id)

        # Local imports after fork
        from chronos.gateway.dispatcher import SessionEnvironment, ASTDispatcher
        from chronos.gateway.shell_parser import ShellParser
        from chronos.gateway.containment import contain_worker
        from chronos.simulation.orchestrator import world_simulation
        from chronos.simulation.event_bus import CommandStarted, CommandSucceeded, CommandFailed, CommandParsed
        import traceback

        env = SessionEnvironment(username=primary_user)
        parser = ShellParser()
        dispatcher = ASTDispatcher(env)
        # Load trusted Python dependencies before restricting the worker root.
        contain_worker('/mnt/honeypot')
        env.honeypot_root = '/'

        # Send initial cwd
        cwd = env.env["PWD"]
        home = env.env["HOME"]
        prompt_cwd = "~" if cwd == home else cwd
        pipe_conn.send({"action": "init", "cwd": prompt_cwd})
        commands_executed = 0
        deadline = time.monotonic() + 3600

        while True:
            if time.monotonic() >= deadline:
                break
            if not r.expire(f"session_pid:{pid}", 120):
                raise RuntimeError('Session attribution expired')

            if pipe_conn.poll(timeout=1.0):
                msg = pipe_conn.recv()
                if msg == "QUIT":
                    break
                elif isinstance(msg, dict) and msg.get("action") == "execute":
                    commands_executed += 1
                    if commands_executed > 1000:
                        break
                    cmd_str = msg["command"]
                    command_id = str(uuid.UUID(msg["command_id"]))
                    # Publish context before any command-triggered FUSE callback.
                    # Session-scoped TTL prevents stale attribution after a crash.
                    command_key = f"session:{session_id}:active_command"
                    r.setex(command_key, 120, command_id)
                    try:
                        from chronos.simulation.orchestrator import world_simulation
                        from chronos.simulation.event_bus import (
                            CommandStarted,
                            CommandSucceeded,
                            CommandFailed,
                            CommandParsed,
                        )

                        ts = time.time()
                        world_simulation.event_bus.publish(
                            CommandStarted(session_id, cmd_str, ts)
                        )

                        sequence = parser.parse(cmd_str)
                        world_simulation.event_bus.publish(
                            CommandParsed(session_id, cmd_str, time.time())
                        )

                        returncode, response = dispatcher.execute_sequence(sequence)

                        if returncode == 0:
                            world_simulation.event_bus.publish(
                                CommandSucceeded(
                                    session_id, cmd_str, response, time.time()
                                )
                            )
                        else:
                            world_simulation.event_bus.publish(
                                CommandFailed(
                                    session_id, cmd_str, response, time.time()
                                )
                            )
                    except Exception as e:
                        returncode = 1
                        logger.exception(
                            "Session command failed session=%s", session_id
                        )
                        response = "bash: Input/output error\n"
                        try:
                            from chronos.simulation.orchestrator import world_simulation
                            from chronos.simulation.event_bus import CommandFailed

                            world_simulation.event_bus.publish(
                                CommandFailed(
                                    session_id, cmd_str, response, time.time()
                                )
                            )
                        except Exception:
                            pass

                    cwd = env.env["PWD"]
                    home = env.env["HOME"]
                    prompt_cwd = "~" if cwd == home else cwd
                    r.delete(command_key)
                    pipe_conn.send(
                        {
                            "returncode": returncode,
                            "response": response,
                            "cwd": prompt_cwd,
                        }
                    )
    except Exception as e:
        import traceback

        traceback.print_exc()
    finally:
        pipe_conn.close()
        try:
            r.delete(f"session_pid:{pid}")
        except:
            pass


class SSHServer(paramiko.ServerInterface):
    def __init__(self, audit_callback=None):
        self.event = threading.Event()
        self.audit_callback = audit_callback

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return OPEN_SUCCEEDED
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        if self.audit_callback:
            self.audit_callback(
                "ssh_login",
                {"username": username, "method": "password"},
            )
        logger.info('[SSH] Password login attempt (credential redacted)')
        return AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        if self.audit_callback:
            self.audit_callback(
                "ssh_login",
                {
                    "username": username,
                    "key_type": key.get_name(),
                    "method": "publickey",
                },
            )
        logger.info(f"[SSH] Key auth: {username}")
        return AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return "password,publickey"

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes
    ):
        return True

    def check_channel_exec_request(self, channel, command):
        if self.audit_callback:
            self.audit_callback("ssh_exec", {"command": command.decode("utf-8")})
        logger.info(f"[SSH] Exec: {command}")
        return False  # Exec channels are not yet supported; reject explicitly.


class SSHHoneypot:
    def __init__(self, host="0.0.0.0", port=2222, hostkey_path=None, db_layer=None):
        self.host = host
        self.port = port
        self.hostkey_path = hostkey_path or self._generate_hostkey()
        self.db_layer = db_layer
        self.running = False
        self._connections = threading.BoundedSemaphore(32)

    def _generate_hostkey(self):
        key_path = "/tmp/chronos_ssh_host_key"
        if not os.path.exists(key_path):
            logger.info("[SSH] Generating host key...")
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(key_path)
        return key_path

    def audit_log(self, event_type, data):
        logger.info(f"[AUDIT] {event_type}: {data}")
        session_id = data.get("session_id", None)
        if self.db_layer and session_id:
            self.db_layer.log_operation(session_id, event_type, "", 0, data)

    def handle_client(self, client_socket, addr):
        logger.info(f"[SSH] Connection from {addr}")
        session_id = str(uuid.uuid4())
        logger.info(f"[SSH] Session assigned: {session_id} from {addr}")

        client_socket.settimeout(120)
        worker_proc = None
        parent_conn = None
        transport = None

        try:
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(paramiko.RSAKey(filename=self.hostkey_path))

            server = SSHServer(
                audit_callback=lambda kind, data: self.audit_log(
                    kind, {**data, "session_id": session_id, "attacker_ip": addr[0]}
                )
            )
            transport.start_server(server=server)

            channel = transport.accept(20)
            if channel is None:
                logger.warning("[SSH] No channel established")
                return

            server.event.wait(10)

            if not server.event.is_set():
                logger.warning("[SSH] Client never requested shell")
                return

            ubuntu_version = _profile.ubuntu_version if _profile else "24.04"
            kernel_version = _profile.kernel_version if _profile else "6.8.0-51-generic"
            hostname = _profile.hostname if _profile else "web01"
            primary_user = _profile.primary_user if _profile else "ubuntu"

            context = multiprocessing.get_context("spawn")
            parent_conn, child_conn = context.Pipe()
            worker_proc = context.Process(
                target=session_worker, args=(session_id, primary_user, child_conn)
            )
            worker_proc.start()
            child_conn.close()
            channel.settimeout(1)

            # Wait for init from worker
            if not parent_conn.poll(15):
                raise TimeoutError("Session worker startup timed out")
            init_msg = parent_conn.recv()
            prompt_cwd = init_msg.get("cwd", "~")

            channel.send(
                f"Welcome to Ubuntu {ubuntu_version} LTS (GNU/Linux {kernel_version} x86_64)\r\n\r\n".encode()
            )
            channel.send(
                b"The programs included with the Ubuntu system are free software;\r\n"
            )
            channel.send(
                b"the exact distribution terms for each program are described in the\r\n"
            )
            channel.send(b"individual files in /usr/share/doc/*/copyright.\r\n\r\n")
            channel.send(f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode())

            command_buffer = ""
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            last_input = time.monotonic()

            while True:
                if not worker_proc.is_alive():
                    raise RuntimeError('Session worker exited')
                if parent_conn.poll():
                    # No unsolicited worker messages are valid between commands.
                    parent_conn.recv()  # EOF surfaces immediately after worker failure.
                    raise RuntimeError('Unexpected session worker message')
                if time.monotonic() - last_input >= 120:
                    raise TimeoutError('SSH session idle timeout')
                try:
                    data = channel.recv(1024)
                except socket.timeout:
                    continue
                if not data or len(data) == 0:
                    break
                last_input = time.monotonic()

                for char in decoder.decode(data):

                    if char == "\r" or char == "\n":
                        channel.send(b"\r\n")
                        if command_buffer.strip():
                            command_id = str(uuid.uuid4())
                            command_started = time.monotonic()
                            self.audit_log(
                                "ssh_command",
                                {
                                    "command": command_buffer.strip(),
                                    "session_id": session_id,
                                    "command_id": command_id,
                                    "schema_version": 1,
                                    "origin": "participant",
                                },
                            )
                            logger.info(
                                f"[SSH] [{session_id[:8]}] Command: {command_buffer.strip()}"
                            )

                            parent_conn.send(
                                {"action": "execute", "command": command_buffer.strip(),
                                 "command_id": command_id}
                            )
                            if not parent_conn.poll(20):
                                self.audit_log("ssh_command_result", {
                                    "session_id": session_id, "command_id": command_id,
                                    "outcome": "unknown", "reason": "worker_timeout",
                                    "server_elapsed_seconds": time.monotonic() - command_started,
                                })
                                raise TimeoutError("Session worker command timed out")
                            result = parent_conn.recv()
                            response = result.get("response", "")
                            self.audit_log("ssh_command_result", {
                                "session_id": session_id, "command_id": command_id,
                                "exit_status": result.get("returncode"),
                                "outcome": "emulated_success" if result.get("returncode") == 0 else "command_failed",
                                "server_elapsed_seconds": time.monotonic() - command_started,
                                "response_bytes": len(response.encode("utf-8")),
                            })
                            prompt_cwd = result.get("cwd", prompt_cwd)

                            if response:
                                if not response.endswith("\n"):
                                    response += "\n"
                                channel.send(response.replace("\n", "\r\n").encode())

                        command_buffer = ""
                        channel.send(
                            f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode()
                        )
                    elif char == "\x03":  # Ctrl+C
                        channel.send(b"^C\r\n")
                        command_buffer = ""
                        channel.send(
                            f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode()
                        )
                    elif char == "\x7f" or char == "\b":  # Backspace
                        if command_buffer:
                            command_buffer = command_buffer[:-1]
                            channel.send(b"\b \b")
                    else:
                        if len((command_buffer + char).encode('utf-8')) > 8192:
                            raise ValueError("SSH command exceeds input limit")
                        command_buffer += char
                        channel.send(char.encode("utf-8"))

        except Exception as e:
            logger.error(f"[SSH] Error: {e}")
        finally:
            # Fail closed before any worker or external-state cleanup can block.
            if transport is not None:
                transport.close()
            client_socket.close()
            if parent_conn:
                try:
                    parent_conn.send("QUIT")
                except:
                    pass
            if worker_proc:
                worker_proc.join(timeout=2)
                if worker_proc.is_alive():
                    worker_proc.terminate()
                    worker_proc.join(timeout=2)
                try:
                    r = redis.Redis(
                        host=os.environ.get("REDIS_HOST", "localhost"),
                        decode_responses=True,
                        socket_timeout=3,
                        socket_connect_timeout=3,
                    )
                    r.eval(
                        "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0",
                        1,
                        f"session_pid:{worker_proc.pid}",
                        session_id,
                    )
                except Exception:
                    logger.exception("PID mapping cleanup failed")
            if parent_conn:
                parent_conn.close()

            self.audit_log(
                "ssh_disconnect",
                {
                    "session_id": session_id,
                },
            )
            logger.info(f"[SSH] Connection closed: {addr}")

    def start(self):
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(100)

        logger.info(f"[SSH] Honeypot listening on {self.host}:{self.port}")

        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                if not self._connections.acquire(blocking=False):
                    client_socket.close()
                    continue
                client_thread = threading.Thread(
                    target=self._limited_client, args=(client_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            logger.info("[SSH] Shutting down...")
        finally:
            server_socket.close()

    def _limited_client(self, client_socket, addr):
        try:
            self.handle_client(client_socket, addr)
        finally:
            self._connections.release()

    def stop(self):
        self.running = False


if __name__ == "__main__":
    honeypot = SSHHoneypot(port=2222)
    honeypot.start()
