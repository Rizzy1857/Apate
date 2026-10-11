from typing import List, Optional, Tuple

MAX_COMMAND_BYTES = 65536
MAX_TOKENS = 512

class ShellWord(str):
    """A quote-removed word retaining which segments permit variable expansion."""

    def __new__(cls, value: str, segments=None):
        instance = super().__new__(cls, value)
        instance.segments = tuple(segments or ((value, True),))
        return instance

class ASTNode:
    pass

class CommandNode(ASTNode):
    def __init__(self, args: List[str]):
        self.args = args
        self.redirect_out: Optional[Tuple[str, bool]] = None  # (filename, append)
        self.redirect_in: Optional[str] = None
        self.redirect_err: Optional[Tuple[str, bool]] = None
        self.redirections = []

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
    def parse(self, command_string: str) -> SequenceNode:
        if len(command_string.encode("utf-8")) > MAX_COMMAND_BYTES:
            raise ParserError("bash: command length limit exceeded")
        if "\x00" in command_string:
            raise ParserError("bash: invalid null byte")
        tokens = self._tokenize(command_string)

        if len(tokens) > MAX_TOKENS:
            raise ParserError("bash: token limit exceeded")

        if not tokens:
            return SequenceNode([])

        return self._parse_sequence(tokens)

    def _tokenize(self, source: str):
        """Tokenize the supported grammar without discarding quote semantics."""
        tokens = []
        segments = []
        buffer = []
        buffer_expand = None
        word_started = False
        quote = None
        index = 0

        def append_char(char, expand):
            nonlocal buffer_expand, word_started
            word_started = True
            if buffer_expand is not None and buffer_expand != expand:
                segments.append(("".join(buffer), buffer_expand))
                buffer.clear()
            buffer_expand = expand
            buffer.append(char)

        def finish_segment():
            nonlocal buffer_expand
            if buffer:
                segments.append(("".join(buffer), bool(buffer_expand)))
                buffer.clear()
            buffer_expand = None

        def finish_word():
            nonlocal word_started
            finish_segment()
            if word_started:
                tokens.append(ShellWord("".join(text for text, _ in segments), segments))
                segments.clear()
                word_started = False

        while index < len(source):
            char = source[index]
            if quote == "'":
                if char == "'":
                    quote = None
                else:
                    append_char(char, False)
                index += 1
                continue
            if quote == '"':
                if char == '"':
                    quote = None
                    index += 1
                    continue
                if char == "`" or source.startswith("$(", index):
                    raise ParserError("bash: command substitution not supported")
                if char == "\\":
                    if index + 1 >= len(source):
                        raise ParserError("bash: syntax error: trailing escape")
                    append_char(source[index + 1], False)
                    index += 2
                    continue
                append_char(char, True)
                index += 1
                continue

            if char.isspace():
                finish_word()
                index += 1
                continue
            if char in ("'", '"'):
                word_started = True
                quote = char
                index += 1
                continue
            if char == "\\":
                if index + 1 >= len(source):
                    raise ParserError("bash: syntax error: trailing escape")
                append_char(source[index + 1], False)
                index += 2
                continue
            if char == "`" or source.startswith("$(", index):
                raise ParserError("bash: command substitution not supported")
            if source.startswith("<(", index) or source.startswith(">(", index):
                raise ParserError("bash: syntax error near unexpected token '('")

            operator = None
            for candidate in ("&&", "||", ">>", ";", "|", "&", "<", ">"):
                if source.startswith(candidate, index):
                    operator = candidate
                    break
            if operator:
                if operator in (">", "<") and source.startswith("&", index + 1):
                    raise ParserError("bash: file descriptor duplication not supported")
                # An unquoted numeric word immediately before > or >> is an IO number.
                current = "".join(text for text, _ in segments) + "".join(buffer)
                all_expandable = all(expand for _, expand in segments) and (
                    buffer_expand in (None, True)
                )
                if operator in (">", ">>") and current.isdigit() and all_expandable:
                    if current != "2":
                        raise ParserError(
                            f"bash: file descriptor {current} is not supported"
                        )
                    segments.clear()
                    buffer.clear()
                    buffer_expand = None
                    word_started = False
                    tokens.append("2" + operator)
                else:
                    finish_word()
                    tokens.append(operator)
                index += len(operator)
                continue

            append_char(char, True)
            index += 1

        if quote is not None:
            raise ParserError("bash: syntax error: unmatched quote")
        finish_word()
        return tokens

    def _parse_sequence(self, tokens: List[str]) -> SequenceNode:
        pipelines = []
        current_pipeline_tokens = []
        current_op = None

        for token in tokens:
            if type(token) is str and token == '&':
                raise ParserError("bash: background execution not supported")
            if type(token) is str and token in (';', '&&', '||'):
                if not current_pipeline_tokens:
                    raise ParserError(f"bash: syntax error near unexpected token '{token}'")
                pipeline = self._parse_pipeline(current_pipeline_tokens)
                pipelines.append((pipeline, current_op))
                current_pipeline_tokens = []
                current_op = token
            else:
                current_pipeline_tokens.append(token)

        if current_pipeline_tokens:
            pipeline = self._parse_pipeline(current_pipeline_tokens)
            pipelines.append((pipeline, current_op))
        elif current_op is not None:
            raise ParserError("bash: syntax error near unexpected token 'newline'")

        return SequenceNode(pipelines)

    def _parse_pipeline(self, tokens: List[str]) -> PipelineNode:
        commands = []
        current_command_tokens = []

        for token in tokens:
            if type(token) is str and token == '|':
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
            if type(token) is str and token in ('>', '>>', '<', '2>', '2>>'):
                if i + 1 >= len(tokens) or not isinstance(tokens[i + 1], ShellWord):
                    raise ParserError(f"bash: syntax error near unexpected token 'newline'")
                target = tokens[i + 1]
                if token == '>':
                    cmd.redirect_out = (target, False)
                    cmd.redirections.append(("stdout", target, False))
                elif token == '>>':
                    cmd.redirect_out = (target, True)
                    cmd.redirections.append(("stdout", target, True))
                elif token == '<':
                    cmd.redirect_in = target
                    cmd.redirections.append(("stdin", target, False))
                elif token == '2>':
                    cmd.redirect_err = (target, False)
                    cmd.redirections.append(("stderr", target, False))
                elif token == '2>>':
                    cmd.redirect_err = (target, True)
                    cmd.redirections.append(("stderr", target, True))
                i += 2
            elif type(token) is str and token in (';', '&&', '||', '|', '&'):
                raise ParserError(f"bash: syntax error near unexpected token '{token}'")
            else:
                args.append(token)
                i += 1

        if not args:
            raise ParserError("bash: redirection without a command is not supported")

        cmd.args = args
        return cmd
