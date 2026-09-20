import os
import re
import redis
import json
import time
import shutil
import errno
import logging
import itertools
from contextlib import ExitStack

logger = logging.getLogger(__name__)
MAX_IO_BYTES = 1024 * 1024
import stat as pystat
from typing import Dict, Any, List, Tuple
from chronos.gateway.shell_parser import SequenceNode, PipelineNode, CommandNode
from chronos.intelligence.ubuntu_profile import UbuntuProfile


class SessionEnvironment:
    def __init__(self, username="ubuntu", honeypot_root="/mnt/honeypot"):
        self.honeypot_root = os.path.abspath(honeypot_root)
        self.cwd = f"/home/{username}"
        self.username = username
        self.profile = UbuntuProfile()
        self.started = time.monotonic()
        self.env = {
            "HOME": f"/home/{username}",
            "USER": username,
            "SHELL": "/bin/bash",
            "HOSTNAME": self.profile.hostname,
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
            "TERM": "xterm-256color",
            "PWD": f"/home/{username}",
            "OLDPWD": f"/home/{username}",
        }


    def expand_vars(self, arg: str) -> str:
        def replace(match):
            var = match.group(1)
            return self.env.get(var, "")

        return re.sub(r"\$([a-zA-Z_][a-zA-Z0-9_]*)", replace, arg)

    def resolve_path(self, path: str) -> str:
        if not isinstance(path, str) or "\x00" in path or len(path) > 4096:
            raise OSError(errno.EINVAL, "Invalid argument")
        if not path.startswith("/"):
            path = os.path.join(self.cwd, path)
        virtual = os.path.normpath("/" + path.lstrip("/"))
        target = os.path.join(self.honeypot_root, virtual.lstrip("/"))
        # The current FUSE implementation does not support symlinks. Refuse any
        # actual runtime symlink rather than following it into the host.
        cursor = self.honeypot_root
        if os.path.islink(cursor):
            raise OSError(errno.EACCES, "Permission denied")
        for part in virtual.split("/"):
            if part:
                cursor = os.path.join(cursor, part)
                if os.path.islink(cursor):
                    raise OSError(errno.EACCES, "Permission denied")
        if os.path.commonpath([self.honeypot_root, target]) != self.honeypot_root:
            raise OSError(errno.EACCES, "Permission denied")
        return target


class CommandRegistry:
    def __init__(self, env: SessionEnvironment):
        self.env = env
        self.handlers = {
            "cd": self._handle_cd,
            "pwd": self._handle_pwd,
            "export": self._handle_export,
            "env": self._handle_env,
            "printenv": self._handle_env,
            "unset": self._handle_unset,
            "echo": self._handle_echo,
            "whoami": self._handle_whoami,
            "id": self._handle_id,
            "hostname": self._handle_hostname,
            "uname": self._handle_uname,
            "free": self._handle_free,
            "top": self._handle_top,
            "ps": self._handle_ps,
            "ss": self._handle_ss,
            "df": self._handle_df,
            "ls": self._handle_ls,
            "cat": self._handle_cat,
            "find": self._handle_find,
            "grep": self._handle_grep,
            "head": self._handle_head,
            "tail": self._handle_tail,
            "stat": self._handle_stat,
            "touch": self._handle_touch,
            "mkdir": self._handle_mkdir,
            "rm": self._handle_rm,
            "rmdir": self._handle_rmdir,
            "cp": self._handle_cp,
            "mv": self._handle_mv,
        }
        self.blocked = {
            "bash",
            "sh",
            "python",
            "python3",
            "perl",
            "curl",
            "wget",
            "nc",
            "netcat",
            "socat",
            "ruby",
            "php",
        }

    def handle(
        self, cmd: str, args: List[str], stdin: bytes = b""
    ) -> Tuple[int, bytes, bytes]:
        if cmd in self.blocked:
            return 127, b"", f"bash: {cmd}: command not found\n".encode()
        if cmd in self.handlers:
            try:
                code, out, err = self.handlers[cmd](args, stdin)
                if len(out) + len(err) > MAX_IO_BYTES:
                    return 1, b"", b"bash: output limit exceeded\n"
                return code, out, err
            except OSError as exc:
                return (
                    1,
                    b"",
                    f"{cmd}: {os.strerror(exc.errno or errno.EIO)}\n".encode(),
                )
            except Exception:
                logger.exception("Emulator command failed: %s", cmd)
                return 1, b"", f"{cmd}: Input/output error\n".encode()
        # Strict emulator: anything unknown is command not found
        return 127, b"", f"bash: {cmd}: command not found\n".encode()

    def _handle_cd(self, args, stdin):
        target = args[0] if args else self.env.env["HOME"]
        real_target = self.env.resolve_path(target)
        if os.path.isdir(real_target):
            self.env.env["OLDPWD"] = self.env.env["PWD"]
            if target.startswith("/"):
                self.env.env["PWD"] = os.path.normpath(target)
            else:
                self.env.env["PWD"] = os.path.normpath(
                    os.path.join(self.env.env["PWD"], target)
                )
            self.env.cwd = self.env.env["PWD"]
            return 0, b"", b""
        else:
            return 1, b"", f"bash: cd: {target}: No such file or directory\n".encode()

    def _handle_pwd(self, args, stdin):
        return 0, (self.env.env["PWD"] + "\n").encode(), b""

    def _handle_export(self, args, stdin):
        for arg in args:
            if "=" in arg:
                key, val = arg.split("=", 1)
                if key not in {"PWD", "OLDPWD", "HOME", "USER", "HOSTNAME"}:
                    self.env.env[key] = val
        return 0, b"", b""

    def _handle_env(self, args, stdin):
        out = "".join(f"{k}={v}\n" for k, v in self.env.env.items())
        return 0, out.encode(), b""

    def _handle_unset(self, args, stdin):
        for arg in args:
            if arg not in {"PWD", "OLDPWD", "HOME", "USER", "HOSTNAME"}:
                self.env.env.pop(arg, None)
        return 0, b"", b""

    def _handle_echo(self, args, stdin):
        return 0, (" ".join(args) + "\n").encode(), b""

    def _handle_whoami(self, args, stdin):
        return 0, (self.env.env["USER"] + "\n").encode(), b""

    def _handle_id(self, args, stdin):
        flags = ''.join(a[1:] for a in args if a.startswith('-'))
        names = [a for a in args if not a.startswith('-')]
        modes = [c for c in flags if c in 'ugG']
        if (any(c not in 'ugGn' for c in flags) or len(modes) > 1
                or ('n' in flags and not modes) or len(names) > 1):
            return 1, b'', b'id: unsupported option combination\n'
        name = names[0] if names else self.env.username
        user = next((u for u in self.env.profile.users if u['name'] == name), None)
        if user is None:
            return 1, b'', f'id: {name}: no such user\n'.encode()
        gid = int(user['gid'])
        groups = {int(g['gid']): g['name'] for g in self.env.profile.groups
                  if name in g.get('members', []) or int(g['gid']) == gid}
        groups.setdefault(gid, str(gid))
        ordered = [gid] + sorted(k for k in groups if k != gid)
        if modes:
            named = 'n' in flags
            if modes[0] == 'u':
                value = name if named else str(user['uid'])
            elif modes[0] == 'g':
                value = groups[gid] if named else str(gid)
            else:
                value = ' '.join(groups[k] if named else str(k) for k in ordered)
            return 0, (value + '\n').encode(), b''
        memberships = ','.join(f'{key}({groups[key]})' for key in ordered)
        return 0, f"uid={user['uid']}({name}) gid={gid}({groups[gid]}) groups={memberships}\n".encode(), b''

    def _handle_hostname(self, args, stdin):
        return 0, (self.env.env["HOSTNAME"] + "\n").encode(), b""

    def _handle_uname(self, args, stdin):
        if "-a" in args:
            return (
                0,
                f"Linux {self.env.profile.hostname} {self.env.profile.kernel_version} #62-Ubuntu SMP x86_64 GNU/Linux\n".encode(),
                b"",
            )
        return 0, b"Linux\n", b""

    def _get_entropy(self) -> Dict[str, Any]:
        return {
            "uptime": str(1209600 + int(time.monotonic() - self.env.started)),
            "cpu_usage": "2.0", "load1": "0.02", "load5": "0.04", "load15": "0.05",
            "mem_total": str(16384 * 1024), "mem_free": str(8192 * 1024),
            "mem_cached": str(4096 * 1024),
        }

    def _handle_free(self, args, stdin):
        state = self._get_entropy()
        total = int(state["mem_total"])
        free = int(state["mem_free"])
        cached = int(state["mem_cached"])
        used = total - free - cached
        total_mb = total // 1024
        used_mb = used // 1024
        free_mb = free // 1024
        shared_mb = 12
        buff_cache_mb = cached // 1024
        available_mb = free_mb + buff_cache_mb
        out = f"               total        used        free      shared  buff/cache   available\n"
        out += f"Mem:           {total_mb}Mi       {used_mb}Mi       {free_mb}Mi        {shared_mb}Mi       {buff_cache_mb}Mi       {available_mb}Mi\n"
        out += f"Swap:             0B          0B          0B\n"
        return 0, out.encode(), b""

    def _processes(self, command):
        rows = [(1, 'root', 'S', 'systemd')]
        for index, service in enumerate(self.env.profile.running_services):
            owner = 'www-data' if service == 'nginx' else 'root'
            rows.append((100 + index, owner, 'S', 'sshd' if service == 'ssh' else service))
        rows.extend([(982, self.env.username, 'S', 'bash'), (994, self.env.username, 'R', command)])
        return rows

    def _handle_top(self, args, stdin):
        state = self._get_entropy()
        rows = self._processes('top')
        total, free, cached = (int(state[k]) // 1024 for k in ('mem_total', 'mem_free', 'mem_cached'))
        out = f"top - {time.strftime('%H:%M:%S', time.gmtime())} up {int(state['uptime'])//86400} days, 1 user, load average: {state['load1']}, {state['load5']}, {state['load15']}\n"
        out += f"Tasks: {len(rows)} total, 1 running, {len(rows)-1} sleeping, 0 stopped, 0 zombie\n"
        out += "%Cpu(s): 2.0 us, 0.5 sy, 0.0 ni, 97.5 id, 0.0 wa, 0.0 hi, 0.0 si, 0.0 st\n"
        out += f"MiB Mem : {total:.1f} total, {free:.1f} free, {total-free-cached:.1f} used, {cached:.1f} buff/cache\n"
        out += f"MiB Swap: 0.0 total, 0.0 free, 0.0 used. {free+cached:.1f} avail Mem\n"
        out += "PID USER S COMMAND\n"
        out += ''.join(f"{pid} {user} {state} {name}\n" for pid, user, state, name in rows)
        return 0, out.encode(), b''

    def _handle_ps(self, args, stdin):
        rows = self._processes('ps')
        if args:
            if any(a not in ('aux', '-aux', '-ef', '-e') for a in args):
                return 1, b'', b'ps: unsupported option\n'
            out = "USER PID STAT COMMAND\n"
            out += ''.join(f"{user} {pid} {state} {name}\n" for pid, user, state, name in rows)
        else:
            out = "  PID TTY          TIME CMD\n"
            out += ''.join(f"{pid:5} pts/0    00:00:00 {name}\n" for pid, _, _, name in rows[-2:])
        return 0, out.encode(), b''

    def _handle_ss(self, args, stdin):
        out = "Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port\n"
        for port in self.env.profile.open_ports:
            out += f"{port['proto']} LISTEN 0 128 0.0.0.0:{port['port']} 0.0.0.0:*\n"
        return 0, out.encode(), b""

    def _handle_df(self, args, stdin):
        drives = json.loads(self.env.profile.build_machine_state()['mounted_drives'])
        out = 'Filesystem 1K-blocks Used Available Use% Mounted on\n'
        for drive in drives:
            total = int(float(drive['size_gb']) * 1024 * 1024)
            used = total // 10
            out += f"{drive['device']} {total} {used} {total-used} 10% {drive['mountpoint']}\n"
        return 0, out.encode(), b""

    def _owner_names(self, info):
        users = {int(u['uid']): u['name'] for u in self.env.profile.users}
        groups = {int(g['gid']): g['name'] for g in self.env.profile.groups}
        return users.get(info.st_uid, str(info.st_uid)), groups.get(info.st_gid, str(info.st_gid))

    def _handle_ls(self, args, stdin):
        flags = [a for a in args if a.startswith("-")]
        paths = [a for a in args if not a.startswith("-")]
        target = paths[0] if paths else self.env.env["PWD"]
        real_target = self.env.resolve_path(target)
        try:
            if os.path.isdir(real_target):
                entries = os.listdir(real_target)
                if "-a" not in flags and "-la" not in flags and "-al" not in flags:
                    entries = [e for e in entries if not e.startswith(".")]
                if any('l' in flag for flag in flags):
                    rows = []
                    for entry in sorted(entries):
                        info = os.stat(os.path.join(real_target, entry))
                        user, group = self._owner_names(info)
                        stamp = time.strftime('%b %d %H:%M', time.gmtime(info.st_mtime))
                        rows.append(f'{pystat.filemode(info.st_mode)} {info.st_nlink} {user} {group} {info.st_size} {stamp} {entry}')
                    out = '\n'.join(rows) + '\n'
                else:
                    out = "\n".join(sorted(entries)) + "\n"
                if not entries:
                    out = ""
                return 0, out.encode(), b""
            elif os.path.exists(real_target):
                if any('l' in flag for flag in flags):
                    info = os.stat(real_target)
                    user, group = self._owner_names(info)
                    stamp = time.strftime('%b %d %H:%M', time.gmtime(info.st_mtime))
                    return 0, f'{pystat.filemode(info.st_mode)} {info.st_nlink} {user} {group} {info.st_size} {stamp} {target}\n'.encode(), b''
                return 0, (os.path.basename(target) + "\n").encode(), b""
            else:
                return (
                    1,
                    b"",
                    f"ls: cannot access '{target}': No such file or directory\n".encode(),
                )
        except Exception as e:
            return (
                1,
                b"",
                f"ls: {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
            )

    def _handle_cat(self, args, stdin):
        if not args:
            return 0, stdin, b""
        out = b""
        err = b""
        ret = 0
        for arg in args:
            real_target = self.env.resolve_path(arg)
            try:
                if os.path.isdir(real_target):
                    err += f"cat: {arg}: Is a directory\n".encode()
                    ret = 1
                else:
                    with open(real_target, "rb") as f:
                        out += f.read(MAX_IO_BYTES - len(out) + 1)
                    if len(out) > MAX_IO_BYTES:
                        return 1, b'', b'cat: output limit exceeded\n'
            except FileNotFoundError:
                err += f"cat: {arg}: No such file or directory\n".encode()
                ret = 1
            except Exception as e:
                err += f"cat: {arg}: {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode()
                ret = 1
        return ret, out, err

    def _handle_find(self, args, stdin):
        # Extremely simplified find
        target = (
            args[0] if args and not args[0].startswith("-") else self.env.env["PWD"]
        )
        real_target = self.env.resolve_path(target)
        if not os.path.exists(real_target):
            return 1, b"", f"find: ‘{target}’: No such file or directory\n".encode()
        out = target + "\n"
        if os.path.isdir(real_target):
            for root, dirs, files in os.walk(real_target):
                rel_root = root.replace(real_target, target, 1)
                for d in dirs:
                    out += os.path.join(rel_root, d) + "\n"
                for f in files:
                    out += os.path.join(rel_root, f) + "\n"
                if len(out) > MAX_IO_BYTES:
                    raise OSError(errno.EFBIG, "File too large")
        return 0, out.encode(), b""

    def _handle_grep(self, args, stdin):
        if not args:
            return 2, b"", b"grep: missing pattern\n"
        if args[0] == '--':
            args = args[1:]
        if not args or args[0].startswith('-'):
            return 2, b"", b"grep: unsupported option or missing pattern\n"
        pattern, files = args[0], args[1:]
        out, err = bytearray(), bytearray()
        for name in files or [None]:
            try:
                if name is None:
                    content = stdin
                else:
                    with open(self.env.resolve_path(name), 'rb') as stream:
                        content = stream.read(MAX_IO_BYTES + 1)
                if len(content) > MAX_IO_BYTES:
                    raise OSError(errno.EFBIG, 'File too large')
                for line in content.decode('utf-8', errors='replace').splitlines():
                    if pattern in line:
                        prefix = f"{name}:" if len(files) > 1 else ""
                        out.extend((prefix + line + "\n").encode())
                        if len(out) > MAX_IO_BYTES:
                            return 2, b"", b"grep: output limit exceeded\n"
            except OSError as exc:
                err.extend(f"grep: {name}: {os.strerror(exc.errno or errno.EIO)}\n".encode())
        return (2 if err else 0 if out else 1), bytes(out), bytes(err)

    def _handle_head(self, args, stdin):
        return self._handle_lines(args, stdin, tail=False)

    def _handle_tail(self, args, stdin):
        return self._handle_lines(args, stdin, tail=True)

    def _handle_lines(self, args, stdin, *, tail):
        command = 'tail' if tail else 'head'
        count = 10
        args = list(args)
        if args and args[0] == '-n':
            if len(args) < 2 or not args[1].isdigit():
                return 1, b"", f"{command}: invalid line count\n".encode()
            count, args = int(args[1]), args[2:]
        if args and args[0] == '--':
            args = args[1:]
        elif any(name.startswith('-') for name in args):
            return 1, b"", f"{command}: unsupported option\n".encode()
        out, err = bytearray(), bytearray()
        for name in args or [None]:
            try:
                if name is None:
                    content = stdin
                else:
                    with open(self.env.resolve_path(name), 'rb') as stream:
                        content = stream.read(MAX_IO_BYTES + 1)
                if len(content) > MAX_IO_BYTES:
                    raise OSError(errno.EFBIG, 'File too large')
                lines = content.splitlines(keepends=True)
                selected = (lines[-count:] if tail else lines[:count]) if count else []
                out.extend(b''.join(selected))
                if len(out) > MAX_IO_BYTES:
                    return 1, b"", f"{command}: output limit exceeded\n".encode()
            except OSError as exc:
                err.extend(f"{command}: {name}: {os.strerror(exc.errno or errno.EIO)}\n".encode())
        return int(bool(err)), bytes(out), bytes(err)

    def _handle_stat(self, args, stdin):
        if not args:
            return 1, b"", b"stat: missing operand\n"
        out = ""
        for arg in args:
            real = self.env.resolve_path(arg)
            try:
                s = os.stat(real)
                out += f"  File: {arg}\n"
                out += f"  Size: {s.st_size}\tBlocks: {s.st_blocks}\tIO Block: {s.st_blksize}\n"
                out += f"Device: 801h/2049d\tInode: {s.st_ino}\tLinks: {s.st_nlink}\n"
                user, group = self._owner_names(s)
                out += f'Access: ({pystat.S_IMODE(s.st_mode):04o}/{pystat.filemode(s.st_mode)})\tUid: ({s.st_uid}/{user})\tGid: ({s.st_gid}/{group})\n'
                for label, value in (('Access', s.st_atime), ('Modify', s.st_mtime), ('Change', s.st_ctime)):
                    stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(value))
                    out += f'{label}: {stamp} +0000\n'
            except Exception as e:
                return (
                    1,
                    b"",
                    f"stat: cannot stat '{arg}': {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
                )
        return 0, out.encode(), b""

    def _handle_touch(self, args, stdin):
        if not args:
            return 1, b"", b"touch: missing file operand\n"
        for arg in args:
            real = self.env.resolve_path(arg)
            try:
                with open(real, "a"):
                    os.utime(real, None)
            except Exception as e:
                return (
                    1,
                    b"",
                    f"touch: cannot touch '{arg}': {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
                )
        return 0, b"", b""

    def _handle_mkdir(self, args, stdin):
        if not args:
            return 1, b"", b"mkdir: missing operand\n"
        for arg in args:
            real = self.env.resolve_path(arg)
            try:
                os.mkdir(real)
            except Exception as e:
                return (
                    1,
                    b"",
                    f"mkdir: cannot create directory '{arg}': {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
                )
        return 0, b"", b""

    def _handle_rm(self, args, stdin):
        if not args:
            return 1, b"", b"rm: missing operand\n"
        recursive = "-r" in args or "-rf" in args
        files = [a for a in args if not a.startswith("-")]
        for arg in files:
            real = self.env.resolve_path(arg)
            try:
                if os.path.isdir(real):
                    if recursive:
                        shutil.rmtree(real)
                    else:
                        return (
                            1,
                            b"",
                            f"rm: cannot remove '{arg}': Is a directory\n".encode(),
                        )
                else:
                    os.unlink(real)
            except Exception as e:
                if "-f" not in args and "-rf" not in args:
                    return (
                        1,
                        b"",
                        f"rm: cannot remove '{arg}': {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
                    )
        return 0, b"", b""

    def _handle_rmdir(self, args, stdin):
        if not args:
            return 1, b"", b"rmdir: missing operand\n"
        for arg in args:
            real = self.env.resolve_path(arg)
            try:
                os.rmdir(real)
            except Exception as e:
                return (
                    1,
                    b"",
                    f"rmdir: failed to remove '{arg}': {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
                )
        return 0, b"", b""

    def _handle_cp(self, args, stdin):
        if len(args) < 2:
            return 1, b"", b"cp: missing file operand\n"
        src = self.env.resolve_path(args[0])
        dst = self.env.resolve_path(args[1])
        try:
            if os.path.isdir(src):
                if "-r" in args:
                    shutil.copytree(src, dst)
                else:
                    return (
                        1,
                        b"",
                        f"cp: -r not specified; omitting directory '{args[0]}'\n".encode(),
                    )
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            return (
                1,
                b"",
                f"cp: {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
            )
        return 0, b"", b""

    def _handle_mv(self, args, stdin):
        if len(args) < 2:
            return 1, b"", b"mv: missing file operand\n"
        src = self.env.resolve_path(args[0])
        dst = self.env.resolve_path(args[1])
        try:
            shutil.move(src, dst)
        except Exception as e:
            return (
                1,
                b"",
                f"mv: {os.strerror(e.errno or errno.EIO) if isinstance(e, OSError) else 'Input/output error'}\n".encode(),
            )
        return 0, b"", b""


class ASTDispatcher:
    def __init__(self, env: SessionEnvironment):
        self.env = env
        self.registry = CommandRegistry(env)

    def execute_sequence(self, sequence: SequenceNode) -> Tuple[int, str]:
        last_returncode = 0
        output_buffer = ""

        if len(sequence.pipelines) > 64:
            return 1, "bash: command limit exceeded\n"
        for pipeline, operator in sequence.pipelines:
            if operator == "&&" and last_returncode != 0:
                continue
            if operator == "||" and last_returncode == 0:
                continue

            returncode, stdout, stderr = self._execute_pipeline(pipeline)
            last_returncode = returncode
            output_buffer += stdout.decode("utf-8", errors="replace")
            output_buffer += stderr.decode("utf-8", errors="replace")
            if len(output_buffer) > MAX_IO_BYTES:
                return 1, "bash: output limit exceeded\n"

        return last_returncode, output_buffer

    def _execute_pipeline(self, pipeline: PipelineNode) -> Tuple[int, bytes, bytes]:
        current_stdin, errors = b"", b""
        returncode = 0
        for cmd_node in pipeline.commands:
            expanded = [self.env.expand_vars(arg) for arg in cmd_node.args]
            try:
                with ExitStack() as stack:
                    outputs = {}
                    # Open redirections before executing; failures prevent command effects.
                    for kind, redirect in (
                        ("stdout", cmd_node.redirect_out),
                        ("stderr", cmd_node.redirect_err),
                    ):
                        if redirect:
                            target = self.env.resolve_path(
                                self.env.expand_vars(redirect[0])
                            )
                            outputs[kind] = stack.enter_context(
                                open(target, "ab" if redirect[1] else "wb")
                            )
                    if cmd_node.redirect_in:
                        target = self.env.resolve_path(
                            self.env.expand_vars(cmd_node.redirect_in)
                        )
                        file = stack.enter_context(open(target, "rb"))
                        current_stdin = file.read(MAX_IO_BYTES + 1)
                        if len(current_stdin) > MAX_IO_BYTES:
                            raise OSError(errno.EFBIG, "File too large")
                    if expanded:
                        returncode, stdout, stderr = self.registry.handle(
                            expanded[0], expanded[1:], current_stdin
                        )
                    else:
                        returncode, stdout, stderr = 0, b"", b""
                    if "stdout" in outputs:
                        outputs["stdout"].write(stdout)
                        stdout = b""
                    if "stderr" in outputs:
                        outputs["stderr"].write(stderr)
                        stderr = b""
                    current_stdin = stdout
                    errors += stderr
            except OSError as exc:
                return 1, b"", f"bash: {os.strerror(exc.errno or errno.EIO)}\n".encode()
        return returncode, current_stdin, errors
