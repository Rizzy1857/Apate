import os
import subprocess
import re
from typing import Dict, Any, List, Optional, Tuple
from chronos.gateway.shell_parser import SequenceNode, PipelineNode, CommandNode

class SessionEnvironment:
    def __init__(self, username="ubuntu", honeypot_root="/mnt/honeypot"):
        self.honeypot_root = honeypot_root
        self.env = {
            "HOME": f"/home/{username}",
            "USER": username,
            "SHELL": "/bin/bash",
            "HOSTNAME": "ubuntu",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
            "TERM": "xterm-256color",
            "PWD": f"/home/{username}",
            "OLDPWD": f"/home/{username}"
        }

    def expand_vars(self, arg: str) -> str:
        # Replace $VAR with env value
        def replace(match):
            var = match.group(1)
            return self.env.get(var, "")
        return re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', replace, arg)

    def resolve_path(self, path: str) -> str:
        if not path.startswith("/"):
            path = os.path.join(self.env["PWD"], path)
        path = os.path.normpath(path)
        real_path = os.path.normpath(os.path.join(self.honeypot_root, path.lstrip("/")))
        if not real_path.startswith(self.honeypot_root):
            return self.honeypot_root
        return real_path

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
        }

    def handle(self, cmd: str, args: List[str], stdin: bytes = b"") -> Tuple[int, bytes, bytes]:
        if cmd in self.handlers:
            return self.handlers[cmd](args, stdin)
        return None  # Indicates it should fall back to subprocess

    def _handle_cd(self, args, stdin):
        target = args[0] if args else self.env.env["HOME"]
        real_target = self.env.resolve_path(target)
        if os.path.isdir(real_target):
            self.env.env["OLDPWD"] = self.env.env["PWD"]
            if target.startswith("/"):
                self.env.env["PWD"] = os.path.normpath(target)
            else:
                self.env.env["PWD"] = os.path.normpath(os.path.join(self.env.env["PWD"], target))
            return 0, b"", b""
        else:
            return 1, b"", f"bash: cd: {target}: No such file or directory\n".encode()

    def _handle_pwd(self, args, stdin):
        return 0, (self.env.env["PWD"] + "\n").encode(), b""

    def _handle_export(self, args, stdin):
        for arg in args:
            if "=" in arg:
                key, val = arg.split("=", 1)
                self.env.env[key] = val
        return 0, b"", b""

    def _handle_env(self, args, stdin):
        out = "".join(f"{k}={v}\n" for k, v in self.env.env.items())
        return 0, out.encode(), b""
        
    def _handle_unset(self, args, stdin):
        for arg in args:
            self.env.env.pop(arg, None)
        return 0, b"", b""

    def _handle_echo(self, args, stdin):
        return 0, (" ".join(args) + "\n").encode(), b""
        
    def _handle_whoami(self, args, stdin):
        return 0, (self.env.env["USER"] + "\n").encode(), b""
        
    def _handle_id(self, args, stdin):
        user = self.env.env["USER"]
        if user == "root":
            out = "uid=0(root) gid=0(root) groups=0(root)\n"
        else:
            out = f"uid=1000({user}) gid=1000({user}) groups=1000({user}),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),122(lpadmin),134(lxd),135(sambashare)\n"
        return 0, out.encode(), b""
        
    def _handle_hostname(self, args, stdin):
        return 0, (self.env.env["HOSTNAME"] + "\n").encode(), b""
        
    def _handle_uname(self, args, stdin):
        if "-a" in args:
            return 0, b"Linux ubuntu 6.8.0-51-generic #62-Ubuntu SMP x86_64 GNU/Linux\n", b""
        return 0, b"Linux\n", b""

class ASTDispatcher:
    def __init__(self, env: SessionEnvironment):
        self.env = env
        self.registry = CommandRegistry(env)

    def execute_sequence(self, sequence: SequenceNode) -> Tuple[int, str]:
        last_returncode = 0
        output_buffer = ""

        for pipeline, operator in sequence.pipelines:
            # Check logical operators
            if operator == '&&' and last_returncode != 0:
                continue
            if operator == '||' and last_returncode == 0:
                continue

            returncode, stdout, stderr = self._execute_pipeline(pipeline)
            last_returncode = returncode
            output_buffer += stdout.decode('utf-8', errors='replace')
            output_buffer += stderr.decode('utf-8', errors='replace')

        return last_returncode, output_buffer

    def _execute_pipeline(self, pipeline: PipelineNode) -> Tuple[int, bytes, bytes]:
        if not pipeline.commands:
            return 0, b"", b""

        # In Python, simulating a pipeline requires chaining process inputs/outputs.
        # But we also have built-in commands. To mix built-ins and subprocesses in a pipe:
        # We will sequentially execute each, feeding stdout to stdin of the next.
        # This keeps the logic simple without requiring complex threading.
        current_stdin = b""
        last_returncode = 0
        final_stdout = b""
        final_stderr = b""

        for i, cmd_node in enumerate(pipeline.commands):
            if not cmd_node.args:
                continue
            
            # Expand variables in arguments
            expanded_args = [self.env.expand_vars(arg) for arg in cmd_node.args]
            command = expanded_args[0]
            args = expanded_args[1:]

            # If there's an explicit redirect_in, we read from that file instead of previous stdout
            if cmd_node.redirect_in:
                real_in = self.env.resolve_path(cmd_node.redirect_in)
                try:
                    with open(real_in, 'rb') as f:
                        current_stdin = f.read()
                except Exception as e:
                    return 1, b"", f"bash: {cmd_node.redirect_in}: {str(e)}\n".encode()

            returncode, stdout, stderr = self._execute_command_single(command, args, current_stdin)
            
            # Handle explicit redirect_out and redirect_err
            if cmd_node.redirect_out:
                real_out = self.env.resolve_path(cmd_node.redirect_out[0])
                mode = 'ab' if cmd_node.redirect_out[1] else 'wb'
                try:
                    with open(real_out, mode) as f:
                        f.write(stdout)
                    stdout = b"" # Consumed by redirect
                except Exception as e:
                    stderr += f"bash: {cmd_node.redirect_out[0]}: {str(e)}\n".encode()

            if cmd_node.redirect_err:
                real_err = self.env.resolve_path(cmd_node.redirect_err[0])
                mode = 'ab' if cmd_node.redirect_err[1] else 'wb'
                try:
                    with open(real_err, mode) as f:
                        f.write(stderr)
                    stderr = b"" # Consumed by redirect
                except Exception as e:
                    stderr += f"bash: {cmd_node.redirect_err[0]}: {str(e)}\n".encode()

            current_stdin = stdout
            last_returncode = returncode
            
            # If it's the last command, store its outputs
            if i == len(pipeline.commands) - 1:
                final_stdout = stdout
                final_stderr = stderr
            else:
                # For intermediate commands, we don't propagate stderr down the pipeline
                final_stderr += stderr

        return last_returncode, final_stdout, final_stderr

    def _execute_command_single(self, cmd: str, args: List[str], stdin: bytes) -> Tuple[int, bytes, bytes]:
        # 1. Check registry (built-ins)
        result = self.registry.handle(cmd, args, stdin)
        if result is not None:
            return result

        # 2. Rewrite paths in arguments pointing to root-like dirs
        rewritten_args = []
        for arg in args:
            # If it looks like a path (starts with / or has / inside), resolve it
            # But we must be careful: some flags have / like --prefix=/opt. We do a simple approach.
            if arg.startswith("/") or ("/" in arg and not arg.startswith("-")):
                rewritten_args.append(self.env.resolve_path(arg))
            else:
                rewritten_args.append(arg)
                
        # 3. Subprocess execution with shell=False
        try:
            # We enforce a timeout and run locally
            proc = subprocess.run(
                [cmd] + rewritten_args,
                input=stdin,
                capture_output=True,
                cwd=self.env.resolve_path(self.env.env["PWD"]),
                env=self.env.env,
                shell=False,
                timeout=15
            )
            return proc.returncode, proc.stdout, proc.stderr
        except FileNotFoundError:
            return 127, b"", f"bash: {cmd}: command not found\n".encode()
        except subprocess.TimeoutExpired:
            return 124, b"", f"bash: {cmd}: timeout\n".encode()
        except Exception as e:
            return 1, b"", f"bash: {cmd}: {str(e)}\n".encode()
