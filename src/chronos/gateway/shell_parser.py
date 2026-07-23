import shlex
import re
from typing import List, Optional, Tuple

class ASTNode:
    pass

class CommandNode(ASTNode):
    def __init__(self, args: List[str]):
        self.args = args
        self.redirect_out: Optional[Tuple[str, bool]] = None  # (filename, append)
        self.redirect_in: Optional[str] = None
        self.redirect_err: Optional[Tuple[str, bool]] = None

    def __repr__(self):
        return f"Command({self.args}, in={self.redirect_in}, out={self.redirect_out})"

class PipelineNode(ASTNode):
    def __init__(self, commands: List[CommandNode]):
        self.commands = commands
        
    def __repr__(self):
        return f"Pipeline({self.commands})"

class SequenceNode(ASTNode):
    def __init__(self, pipelines: List[Tuple[PipelineNode, Optional[str]]]):
        # Tuple of (PipelineNode, operator_that_preceded_it_or_None)
        # e.g., for `a ; b && c`, pipelines=[(a, None), (b, ';'), (c, '&&')]
        self.pipelines = pipelines
        
    def __repr__(self):
        return f"Sequence({self.pipelines})"

class ParserError(Exception):
    pass

class ShellParser:
    def __init__(self):
        # We catch unsupported syntax before deep parsing
        self.unsupported_patterns = [
            (re.compile(r'\$\(.*\)'), "bash: command substitution not supported"),
            (re.compile(r'`.*`'), "bash: command substitution not supported"),
            (re.compile(r'<\(.*\)'), "bash: syntax error near unexpected token '('"),
            (re.compile(r'>\(.*\)'), "bash: syntax error near unexpected token '('"),
        ]

    def parse(self, command_string: str) -> SequenceNode:
        # Pre-check for unsupported constructs to reject them immediately
        for pattern, error_msg in self.unsupported_patterns:
            if pattern.search(command_string):
                raise ParserError(error_msg)

        try:
            lex = shlex.shlex(command_string, posix=True, punctuation_chars='|&;<>')
            lex.wordchars += '-/.~@+_=:$*?#[]{}'
            tokens = list(lex)
        except ValueError as e:
            raise ParserError(f"bash: syntax error: {str(e)}")

        if not tokens:
            return SequenceNode([])

        return self._parse_sequence(tokens)

    def _parse_sequence(self, tokens: List[str]) -> SequenceNode:
        pipelines = []
        current_pipeline_tokens = []
        current_op = None

        for token in tokens:
            if token in (';', '&&', '||'):
                if current_pipeline_tokens:
                    pipeline = self._parse_pipeline(current_pipeline_tokens)
                    pipelines.append((pipeline, current_op))
                current_pipeline_tokens = []
                current_op = token
            else:
                current_pipeline_tokens.append(token)

        if current_pipeline_tokens:
            pipeline = self._parse_pipeline(current_pipeline_tokens)
            pipelines.append((pipeline, current_op))

        return SequenceNode(pipelines)

    def _parse_pipeline(self, tokens: List[str]) -> PipelineNode:
        commands = []
        current_command_tokens = []

        for token in tokens:
            if token == '|':
                if not current_command_tokens:
                    raise ParserError("bash: syntax error near unexpected token '|'")
                commands.append(self._parse_command(current_command_tokens))
                current_command_tokens = []
            else:
                current_command_tokens.append(token)

        if current_command_tokens:
            commands.append(self._parse_command(current_command_tokens))
        elif commands:
            # Trailing pipe
            raise ParserError("bash: syntax error near unexpected token '|'")

        return PipelineNode(commands)

    def _parse_command(self, tokens: List[str]) -> CommandNode:
        args = []
        cmd = CommandNode([])
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ('>', '>>', '<', '2>', '2>>'):
                if i + 1 >= len(tokens):
                    raise ParserError(f"bash: syntax error near unexpected token 'newline'")
                target = tokens[i + 1]
                if token == '>':
                    cmd.redirect_out = (target, False)
                elif token == '>>':
                    cmd.redirect_out = (target, True)
                elif token == '<':
                    cmd.redirect_in = target
                elif token == '2>':
                    cmd.redirect_err = (target, False)
                elif token == '2>>':
                    cmd.redirect_err = (target, True)
                i += 2
            else:
                args.append(token)
                i += 1

        if not args and not (cmd.redirect_in or cmd.redirect_out or cmd.redirect_err):
            pass # this should not happen if tokens is not empty

        cmd.args = args
        return cmd
