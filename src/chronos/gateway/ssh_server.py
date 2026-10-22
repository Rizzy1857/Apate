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
import json

from chronos.core.session_cleanup import (
    LIFECYCLE_KEY,
    acknowledge_disconnect,
    prepare_disconnect,
    register_lifecycle,
)

try:
    from chronos.intelligence.ubuntu_profile import UbuntuProfile as _UbuntuProfile

    _profile = _UbuntuProfile()
except Exception:
    _profile = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChannelWriteError(ConnectionError):
    def __init__(self, message, bytes_sent=0):
        super().__init__(message)
        self.bytes_sent = bytes_sent


def _send_all(channel, payload):
    """Write the complete payload or raise with the locally accepted byte count."""
    payload = bytes(payload)
    sent_total = 0
    while sent_total < len(payload):
        try:
            sent = channel.send(payload[sent_total:])
        except Exception as exc:
            raise ChannelWriteError("SSH channel write failed", sent_total) from exc
        if not isinstance(sent, int) or sent <= 0:
            raise ChannelWriteError("SSH channel closed during write", sent_total)
        if sent > len(payload) - sent_total:
            raise ChannelWriteError("SSH channel reported an invalid write count", sent_total)
        sent_total += sent
    return sent_total


def _refresh_session_pid(client, pid, session_id, ttl=120):
    """Renew an owned, live lease; never resurrect an expired namespace.

    The reaper may already have selected a missing mapping for cleanup, even if
    its lifecycle record still exists. Recreating that mapping races deletion.
    """
    result = client.eval(
        "local owner = redis.call('GET', KEYS[1]); "
        "if not owner then return 0 end; "
        "if owner ~= ARGV[1] then return -1 end; "
        "if redis.call('EXISTS', KEYS[2]) == 0 then return 0 end; "
        "if redis.call('HEXISTS', KEYS[2], 'completed_at') == 1 then return 0 end; "
        "return redis.call('EXPIRE', KEYS[1], ARGV[2])",
        2,
        f"session_pid:{pid}",
        LIFECYCLE_KEY.format(session_id=session_id),
        session_id,
        int(ttl),
    )
    return int(result)


def session_worker(session_id, primary_user, session_origin, pipe_conn):
    """Runs in a separate process per SSH session. Emulates commands and touches FUSE."""
    pid = os.getpid()
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    # DNS after chroot would read resolver files through the honeypot itself.
    # A worker never survives a Redis connection loss; resolve before containment.
    redis_host = socket.gethostbyname(redis_host)
    r = redis.Redis(
        password=os.environ.get("REDIS_PASSWORD") or None,
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
        # Keep a cumulative CPU bound separate from the one-hour wall deadline.
        worker_cpu_seconds = int(os.environ.get("CHRONOS_WORKER_CPU_SECONDS", "300"))
        if not 60 <= worker_cpu_seconds <= 600:
            raise ValueError("CHRONOS_WORKER_CPU_SECONDS must be between 60 and 600")
        resource.setrlimit(
            resource.RLIMIT_CPU, (worker_cpu_seconds, worker_cpu_seconds)
        )
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        # Register PID mapping for FUSE attribution
        r.setex(f"session_pid:{pid}", 120, session_id)

        # Local imports after fork
        from chronos.gateway.dispatcher import SessionEnvironment, ASTDispatcher
        from chronos.gateway.shell_parser import ShellParser, ParserError
        from chronos.gateway.containment import contain_worker
        from chronos.simulation.orchestrator import world_simulation
        from chronos.simulation.event_bus import CommandStarted, CommandSucceeded, CommandFailed, CommandParsed
        import traceback

        env = SessionEnvironment(username=primary_user)
        # Device identity exists for every admitted session, including sessions
        # that never read an AI-backed file. Creation is atomic and persistent.
        env.machine_state = env.profile.get_or_create_machine_state(r, session_id)
        run_id = r.get(f"session:{session_id}:run_id")
        restored_cwd = None
        if run_id:
            import json as _json
            run = r.hgetall(f"chronos:run:{run_id}")
            env.machine_state = _json.loads(run["persona"])
            r.hset(f"chronos:machine_state:{session_id}", mapping=env.machine_state)
            restored_cwd = run.get("cwd")
        from chronos.core.session_context import publish_context
        parser = ShellParser()
        dispatcher = ASTDispatcher(env)
        # Load trusted Python dependencies before restricting the worker root.
        contain_worker('/mnt/honeypot')
        env.honeypot_root = '/'
        if restored_cwd and os.path.isdir(env.resolve_path(restored_cwd)):
            env.cwd = restored_cwd
            env.env["PWD"] = restored_cwd
        publish_context(r, session_id, env)

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
            if _refresh_session_pid(r, pid, session_id) <= 0:
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
                    origin_key = f"session:{session_id}:active_command_origin"
                    r.setex(command_key, 120, command_id)
                    r.setex(origin_key, 120, session_origin)
                    world_raw = r.get('env:world')
                    env.world_state = json.loads(world_raw) if world_raw else None
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

                        returncode, response, stage_results = (
                            dispatcher.execute_sequence_with_stages(sequence)
                        )

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
                    except ParserError as exc:
                        returncode = 2
                        stage_results = []
                        response = str(exc) + "\n"
                        world_simulation.event_bus.publish(
                            CommandFailed(
                                session_id, cmd_str, response, time.time()
                            )
                        )
                    except Exception as e:
                        returncode = 1
                        stage_results = []
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

                    env.last_status = returncode
                    publish_context(r, session_id, env, command_id)
                    cwd = env.env["PWD"]
                    home = env.env["HOME"]
                    prompt_cwd = "~" if cwd == home else cwd
                    r.delete(command_key, origin_key)
                    pipe_conn.send(
                        {
                            "returncode": returncode,
                            "response": response,
                            "cwd": prompt_cwd,
                            "world_snapshot": env.world_state,
                            "stage_results": stage_results,
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
    IDENTITY_POLICY = "accept_any_claim_profile_identity"

    def __init__(self, audit_callback=None, effective_username="ubuntu"):
        self.event = threading.Event()
        self.audit_callback = audit_callback
        self.effective_username = effective_username
        self.claimed_username = None
        self.authentication_method = None

    def identity_metadata(self):
        return {
            "claimed_username": self.claimed_username,
            "effective_username": self.effective_username,
            "identity_mismatch": (
                self.claimed_username is not None
                and self.claimed_username != self.effective_username
            ),
            "identity_policy": self.IDENTITY_POLICY,
        }

    def _accept_authentication(self, username, method, **details):
        self.claimed_username = str(username)
        self.authentication_method = method
        if self.audit_callback:
            self.audit_callback("ssh_login", {
                **self.identity_metadata(),
                "method": method,
                "accepted": True,
                "outcome": "completed",
                "schema_version": 1,
                **details,
            })
        return AUTH_SUCCESSFUL

    def _reject_request(self, request_type, outcome="unsupported", **details):
        if self.audit_callback:
            self.audit_callback("ssh_request", {
                "request_id": str(uuid.uuid4()),
                "request_type": request_type,
                "outcome": outcome,
                "accepted": False,
                "schema_version": 1,
                **self.identity_metadata(),
                **details,
            })

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return OPEN_SUCCEEDED
        self._reject_request("channel", channel_kind=kind, channel_id=chanid)
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        logger.info('[SSH] Password login attempt (credential redacted)')
        return self._accept_authentication(username, "password")

    def check_auth_publickey(self, username, key):
        logger.info(f"[SSH] Key auth: {username}")
        return self._accept_authentication(
            username, "publickey", key_type=key.get_name()
        )

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
        decoded = command.decode("utf-8", errors="replace")
        self._reject_request("exec", command=decoded)
        logger.info(f"[SSH] Exec: {command}")
        return False  # Exec channels are not yet supported; reject explicitly.

    def check_channel_subsystem_request(self, channel, name):
        self._reject_request("subsystem", subsystem=name)
        return False

    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        self._reject_request(
            "direct_tcpip", outcome="denied", channel_id=chanid,
            origin_host=str(origin[0]), origin_port=int(origin[1]),
            destination_host=str(destination[0]), destination_port=int(destination[1]),
        )
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_port_forward_request(self, address, port):
        self._reject_request(
            "remote_port_forward", outcome="denied",
            bind_address=str(address), bind_port=int(port),
        )
        return False


class SSHHoneypot:
    def __init__(self, host="0.0.0.0", port=2222, hostkey_path=None, db_layer=None):
        self.host = host
        self.port = port
        self.hostkey_path = hostkey_path or self._generate_hostkey()
        self.db_layer = db_layer
        self.running = False
        self._connections = threading.BoundedSemaphore(32)

    def _generate_hostkey(self):
        # /var/lib/chronos is a persistent, private deployment volume. Keeping
        # identity here avoids alarming host-key changes after image rebuilds.
        key_path = os.environ.get(
            "APATE_SSH_HOST_KEY", "/var/lib/chronos/ssh_host_rsa_key"
        )
        if not os.path.exists(key_path):
            logger.info("[SSH] Generating host key...")
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(key_path)
            os.chmod(key_path, 0o600)
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
        worker_heartbeat = None
        heartbeat_stop = threading.Event()
        parent_conn = None
        transport = None
        pending_command = None
        server = None
        lifecycle_client = None
        disconnect_outcome = "completed"
        disconnect_reason = "connection_closed"
        primary_user = _profile.primary_user if _profile else "ubuntu"
        session_origin = os.environ.get('APATE_SESSION_ORIGIN',
                                        'scripted_test' if os.environ.get('CHRONOS_TEST_AUDIT') == '1' else 'participant')
        if session_origin not in ('participant', 'scripted_test'):
            client_socket.close()
            raise ValueError('Invalid APATE_SESSION_ORIGIN')

        try:
            transport = paramiko.Transport(client_socket)
            transport.local_version = "SSH-2.0-OpenSSH_" + (
                _profile.package_version("openssh-server") if _profile else None
            or "9.6p1")
            transport.add_server_key(paramiko.RSAKey(filename=self.hostkey_path))

            server = SSHServer(
                audit_callback=lambda kind, data: self.audit_log(
                    kind, {**data, "session_id": session_id, "attacker_ip": addr[0],
                           "origin": session_origin}
                ),
                effective_username=primary_user,
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

            self.audit_log("ssh_session_opened", {
                "session_id": session_id,
                "schema_version": 1,
                "origin": session_origin,
                **server.identity_metadata(),
            })
            lifecycle_client = redis.Redis(
                password=os.environ.get("REDIS_PASSWORD") or None,
                host=os.environ.get("REDIS_HOST", "localhost"),
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            register_lifecycle(
                lifecycle_client, session_id, origin=session_origin,
                identity=server.identity_metadata(),
            )
            if os.environ.get("CHRONOS_PERSISTENT_RUNS") == "1":
                from chronos.core.research_runs import attach_session
                persona = _profile.get_or_create_machine_state(lifecycle_client, session_id)
                run = attach_session(lifecycle_client, session_id, persona)
                self.audit_log("research_run_attached", {
                    "session_id": session_id, "run_id": run["run_id"],
                    "device_id": run["device_id"], "origin": session_origin,
                    "source_revision": os.environ.get("APATE_SOURCE_REVISION"),
                    "configuration_digest": os.environ.get("APATE_CONFIGURATION_DIGEST"),
                    "profile_digest": os.environ.get("APATE_PROFILE_DIGEST"),
                    **server.identity_metadata(),
                })

            ubuntu_version = _profile.ubuntu_version if _profile else "24.04"
            kernel_version = _profile.kernel_version if _profile else "6.8.0-51-generic"
            hostname = _profile.hostname if _profile else "web01"
            context = multiprocessing.get_context("spawn")
            parent_conn, child_conn = context.Pipe()
            worker_proc = context.Process(
                target=session_worker,
                args=(session_id, primary_user, session_origin, child_conn),
            )
            worker_proc.start()
            child_conn.close()

            def refresh_worker_mapping():
                heartbeat_client = redis.Redis(
                    password=os.environ.get("REDIS_PASSWORD") or None,
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    decode_responses=True,
                    socket_timeout=3,
                    socket_connect_timeout=3,
                )
                try:
                    while not heartbeat_stop.wait(30):
                        if not worker_proc.is_alive():
                            return
                        refresh_result = _refresh_session_pid(
                            heartbeat_client, worker_proc.pid, session_id
                        )
                        if refresh_result <= 0:
                            logger.error(
                                "Worker attribution heartbeat rejected session=%s pid=%s result=%s",
                                session_id, worker_proc.pid, refresh_result,
                            )
                            return
                except Exception:
                    logger.exception("Worker attribution heartbeat failed")
                finally:
                    heartbeat_client.close()

            worker_heartbeat = threading.Thread(
                target=refresh_worker_mapping,
                name=f"session-heartbeat-{session_id[:8]}",
                daemon=True,
            )
            worker_heartbeat.start()
            channel.settimeout(1)

            # Wait for init from worker
            if not parent_conn.poll(15):
                raise TimeoutError("Session worker startup timed out")
            init_msg = parent_conn.recv()
            prompt_cwd = init_msg.get("cwd", "~")

            _send_all(channel,
                f"Welcome to Ubuntu {ubuntu_version} LTS (GNU/Linux {kernel_version} x86_64)\r\n\r\n".encode()
            )
            _send_all(channel,
                b"The programs included with the Ubuntu system are free software;\r\n"
            )
            _send_all(channel,
                b"the exact distribution terms for each program are described in the\r\n"
            )
            _send_all(channel, b"individual files in /usr/share/doc/*/copyright.\r\n\r\n")
            _send_all(channel, f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode())

            command_buffer = ""
            discard_line = False
            command_bytes = 0
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

                    if discard_line:
                        # Drain the entire rejected line: no suffix may become a command.
                        if char in ("\r", "\n"):
                            discard_line = False
                            _send_all(channel, f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode())
                        elif char == "\x03":
                            discard_line = False
                            _send_all(channel, f"^C\r\n{primary_user}@{hostname}:{prompt_cwd}$ ".encode())
                        continue

                    if char == "\r" or char == "\n":
                        _send_all(channel, b"\r\n")
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
                                    "origin": session_origin,
                                    **server.identity_metadata(),
                                },
                            )
                            logger.info(
                                f"[SSH] [{session_id[:8]}] Command: {command_buffer.strip()}"
                            )
                            pending_command = (command_id, command_started)

                            parent_conn.send(
                                {"action": "execute", "command": command_buffer.strip(),
                                 "command_id": command_id}
                            )
                            if not parent_conn.poll(20):
                                self.audit_log("ssh_command_result", {
                                    "session_id": session_id, "command_id": command_id,
                                    "outcome": "unknown", "reason": "worker_timeout",
                                    "server_elapsed_seconds": time.monotonic() - command_started,
                                    **server.identity_metadata(),
                                })
                                pending_command = None
                                raise TimeoutError("Session worker command timed out")
                            result = parent_conn.recv()
                            response = result.get("response", "")
                            execution_elapsed = time.monotonic() - command_started
                            prompt_cwd = result.get("cwd", prompt_cwd)

                            generated_bytes = len(response.encode("utf-8"))
                            wire_response = response
                            if wire_response and not wire_response.endswith("\n"):
                                wire_response += "\n"
                            payload = wire_response.replace("\n", "\r\n").encode()
                            transmitted_bytes = 0
                            delivery = "no_response" if not payload else "accepted_by_transport"
                            delivery_reason = None
                            try:
                                if payload:
                                    transmitted_bytes = _send_all(channel, payload)
                            except ChannelWriteError as exc:
                                transmitted_bytes = exc.bytes_sent
                                delivery = "uncertain"
                                delivery_reason = "transport_write_failed"
                                raise
                            finally:
                                self.audit_log("ssh_command_result", {
                                    "session_id": session_id, "command_id": command_id,
                                    "exit_status": result.get("returncode"),
                                    "outcome": "emulated_success" if result.get("returncode") == 0 else "command_failed",
                                    "server_elapsed_seconds": execution_elapsed,
                                    "response_bytes": generated_bytes,
                                    "generated_response_bytes": generated_bytes,
                                    "transport_response_bytes": transmitted_bytes,
                                    "response_delivery": delivery,
                                    "delivery_reason": delivery_reason,
                                    "world_snapshot": result.get("world_snapshot"),
                                    "stage_results": result.get("stage_results", []),
                                    **server.identity_metadata(),
                                })
                                pending_command = None

                        command_buffer = ""
                        command_bytes = 0
                        _send_all(channel,
                            f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode()
                        )
                    elif char == "\x03":  # Ctrl+C
                        _send_all(channel, b"^C\r\n")
                        command_buffer = ""
                        command_bytes = 0
                        _send_all(channel,
                            f"{primary_user}@{hostname}:{prompt_cwd}$ ".encode()
                        )
                    elif char == "\x7f" or char == "\b":  # Backspace
                        if command_buffer:
                            command_bytes -= len(command_buffer[-1].encode("utf-8"))
                            command_buffer = command_buffer[:-1]
                            _send_all(channel, b"\b \b")
                    else:
                        char_bytes = len(char.encode("utf-8"))
                        if command_bytes + char_bytes > 8192:
                            self.audit_log("ssh_request", {
                                "session_id": session_id, "request_id": str(uuid.uuid4()),
                                "request_type": "shell_input", "outcome": "denied",
                                "accepted": False, "reason": "input_limit",
                                "limit_bytes": 8192, "schema_version": 1,
                                "origin": session_origin, **server.identity_metadata(),
                            })
                            command_buffer = ""
                            command_bytes = 0
                            discard_line = True
                            _send_all(channel, b"\r\nbash: command length limit exceeded\r\n")
                            continue
                        command_buffer += char
                        command_bytes += char_bytes
                        _send_all(channel, char.encode("utf-8"))

        except Exception as e:
            disconnect_outcome = (
                "timed_out" if isinstance(e, TimeoutError) else "interrupted"
            )
            disconnect_reason = (
                "session_timeout" if isinstance(e, TimeoutError) else "session_error"
            )
            logger.error(f"[SSH] Error: {e}")
        finally:
            heartbeat_stop.set()
            if worker_heartbeat is not None:
                worker_heartbeat.join(timeout=4)
            # Fail closed before any worker or external-state cleanup can block.
            if transport is not None:
                transport.close()
            client_socket.close()
            if pending_command is not None:
                try:
                    self.audit_log("ssh_command_result", {
                        "session_id": session_id, "command_id": pending_command[0],
                        "outcome": "unknown", "reason": "session_interrupted",
                        "server_elapsed_seconds": time.monotonic() - pending_command[1],
                        **server.identity_metadata(),
                    })
                except Exception:
                    logger.exception('Unable to persist interrupted command outcome')
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
                        password=os.environ.get("REDIS_PASSWORD") or None,
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

            identity = server.identity_metadata() if server is not None else {
                "claimed_username": None,
                "effective_username": primary_user,
                "identity_mismatch": False,
                "identity_policy": SSHServer.IDENTITY_POLICY,
            }
            lifecycle = (
                prepare_disconnect(
                    lifecycle_client, session_id,
                    outcome=disconnect_outcome, reason=disconnect_reason,
                )
                if lifecycle_client is not None else None
            )
            self.audit_log("ssh_disconnect", {
                "session_id": session_id,
                **(lifecycle or identity),
            })
            if lifecycle is not None:
                acknowledge_disconnect(lifecycle_client, session_id)
                lifecycle_client.close()
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
