from __future__ import annotations

from dataclasses import dataclass
import re
import shlex


_CHAIN_OPERATORS = {"&&", "||", ";", "|", "\n"}
_WRAPPERS = {
    ("bash", "-c"),
    ("sh", "-c"),
    ("cmd", "/c"),
    ("cmd.exe", "/c"),
    ("powershell", "-command"),
    ("powershell.exe", "-command"),
    ("pwsh", "-command"),
    ("python", "-c"),
    ("python.exe", "-c"),
}


@dataclass(frozen=True)
class ParsedCommand:
    raw: str
    normalized: str
    tokens: tuple[str, ...]
    wrapper: str | None = None


class CommandParseError(ValueError):
    pass


def parse_commands(command: str) -> list[ParsedCommand]:
    if not isinstance(command, str) or not command.strip():
        raise CommandParseError("command must be a non-empty string")
    if "\x00" in command:
        raise CommandParseError("command contains a NUL byte")

    segments = _split_chained(command)
    parsed: list[ParsedCommand] = []
    for segment in segments:
        parsed.extend(_parse_segment(segment))
    if not parsed:
        raise CommandParseError("no executable command found")
    return parsed


def _parse_segment(segment: str) -> list[ParsedCommand]:
    text = segment.strip()
    if not text:
        return []
    try:
        tokens = tuple(shlex.split(text, posix=True))
    except ValueError as exc:
        raise CommandParseError(str(exc)) from exc
    if not tokens:
        return []

    lowered = tuple(token.lower() for token in tokens)
    if len(tokens) >= 3 and lowered[:2] in _WRAPPERS:
        payload = " ".join(tokens[2:])
        nested = parse_commands(payload)
        return [
            ParsedCommand(
                raw=item.raw,
                normalized=item.normalized,
                tokens=item.tokens,
                wrapper=f"{tokens[0]} {tokens[1]}",
            )
            for item in nested
        ]

    normalized = " ".join(shlex.quote(token) for token in tokens)
    return [ParsedCommand(raw=text, normalized=normalized, tokens=tokens)]


def _split_chained(command: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(command):
        char = command[index]
        if escaped:
            current.append(char)
            escaped = False
            index += 1
            continue
        if char == "\\" and quote != "'":
            current.append(char)
            escaped = True
            index += 1
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            current.append(char)
            index += 1
            continue
        if quote is None:
            pair = command[index : index + 2]
            operator = pair if pair in {"&&", "||"} else char
            if operator in _CHAIN_OPERATORS:
                segments.append("".join(current))
                current = []
                index += len(operator)
                continue
        current.append(char)
        index += 1
    if quote is not None:
        raise CommandParseError("unclosed quote")
    segments.append("".join(current))
    return [segment for segment in segments if segment.strip()]


def contains_obfuscation(command: str) -> bool:
    lowered = command.lower()
    return bool(
        re.search(r"(?:frombase64string|encodedcommand|\s-enc(?:odedcommand)?\b)", lowered)
        or re.search(r"\$\(|`[^`]+`", command)
        or re.search(r"\b(?:eval|exec)\s+", lowered)
    )
