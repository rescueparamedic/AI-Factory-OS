from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .command_parser import ParsedCommand, contains_obfuscation
from .context import EvaluationContext, PROTECTED_BRANCHES, is_feature_branch, path_is_inside_repository
from .models import ApprovalDecision


@dataclass(frozen=True)
class RuleMatch:
    decision: ApprovalDecision
    risk_level: str
    rule_id: str
    reason: str


DENY = ApprovalDecision.DENY
ASK = ApprovalDecision.ASK_USER
ALLOW = ApprovalDecision.AUTO_APPROVE


def classify(command: ParsedCommand, context: EvaluationContext) -> RuleMatch:
    tokens = tuple(token.lower() for token in command.tokens)
    text = " ".join(tokens)

    deny = _deny_rule(tokens, text, command)
    if deny:
        return deny
    context_guard = _context_guard(tokens, context)
    if context_guard:
        return context_guard
    ask = _ask_rule(tokens, text, context)
    if ask:
        return ask
    safe = _safe_rule(tokens, context)
    if safe:
        return safe
    return RuleMatch(ASK, "medium", "AGV2-A999", "Unknown or unclassified command requires user review.")


def _deny_rule(tokens: tuple[str, ...], text: str, command: ParsedCommand) -> RuleMatch | None:
    if _starts(tokens, "git", "reset", "--hard"):
        return _match(DENY, "critical", "AGV2-D001", "Hard reset can discard tracked work.")
    if _starts(tokens, "git", "clean") and any(token.startswith("-") and "f" in token for token in tokens[2:]):
        return _match(DENY, "critical", "AGV2-D001", "Git clean with force can delete untracked work.")
    if _starts(tokens, "git", "push") and any(token in {"--force", "-f", "--force-with-lease"} for token in tokens):
        return _match(DENY, "critical", "AGV2-D001", "Force push can overwrite remote history.")
    if _starts(tokens, "git", "push") and _deletes_protected_remote_ref(tokens):
        return _match(DENY, "critical", "AGV2-D001", "Protected remote branches cannot be deleted.")
    if _starts(tokens, "git", "branch") and any(token in {"-d", "-D", "--delete"} for token in command.tokens[2:]):
        targets = {token.lower() for token in command.tokens[3:]}
        if targets & PROTECTED_BRANCHES:
            return _match(DENY, "critical", "AGV2-D001", "Protected branches cannot be deleted.")
    if tokens and tokens[0] in {"rm", "rmdir", "remove-item", "del"}:
        if _destructive_filesystem_target(tokens):
            return _match(DENY, "critical", "AGV2-D002", "Recursive deletion of a root, home, or repository tree is forbidden.")
    if _credential_exfiltration(text):
        return _match(DENY, "critical", "AGV2-D003", "Potential credential exfiltration or security bypass detected.")
    if _reads_sensitive_file(tokens):
        return _match(DENY, "critical", "AGV2-D003", "Reading plaintext credential files through a command is forbidden.")
    if contains_obfuscation(command.raw):
        return _match(DENY, "high", "AGV2-D004", "Obfuscated or policy-bypass execution is forbidden.")
    return None


def _context_guard(tokens: tuple[str, ...], context: EvaluationContext) -> RuleMatch | None:
    if not context.cwd_in_repository and _is_write_or_git_mutation(tokens):
        return _match(ASK, "high", "AGV2-A004", "Write or Git mutation outside the repository requires user approval.")
    if context.environment in {"prod", "production"} and not _is_read_only(tokens):
        return _match(ASK, "high", "AGV2-A005", "Production environment actions cannot be auto-approved.")
    return None


def _ask_rule(tokens: tuple[str, ...], text: str, context: EvaluationContext) -> RuleMatch | None:
    if not tokens:
        return _match(ASK, "medium", "AGV2-A999", "Empty command requires user review.")
    if tokens[0] in {"curl", "wget", "invoke-webrequest", "scp", "ftp", "ssh"}:
        return _match(ASK, "high", "AGV2-A002", "External network or data transfer requires user approval.")
    if _starts(tokens, "pip", "install") or _starts(tokens, "python", "-m", "pip", "install"):
        return _match(ASK, "medium", "AGV2-A003", "Dependency installation changes the development environment.")
    if tokens[0] in {"npm", "pnpm", "yarn", "winget", "choco", "apt", "apt-get"} and "install" in tokens:
        return _match(ASK, "medium", "AGV2-A003", "Dependency or system configuration changes require approval.")
    if _starts(tokens, "git", "push"):
        target = _git_push_target(tokens)
        if target in PROTECTED_BRANCHES:
            return _match(ASK, "high", "AGV2-A001", "Pushing a protected branch requires user approval.")
        if target and target.startswith("feature/") and is_feature_branch(context.branch):
            return None
        return _match(ASK, "medium", "AGV2-A001", "Push target or branch context is not a verified feature workflow.")
    if _starts(tokens, "git", "merge"):
        return _match(ASK, "high" if context.branch in PROTECTED_BRANCHES else "medium", "AGV2-A001", "Merge operations require user approval.")
    if _starts(tokens, "git", "checkout") or _starts(tokens, "git", "switch"):
        if _creates_feature_branch(tokens):
            return None
        return _match(ASK, "medium", "AGV2-A001", "Branch checkout outside a new feature branch requires approval.")
    if _starts(tokens, "git", "add"):
        paths = [token for token in tokens[2:] if not token.startswith("-")]
        if _safe_staging_paths(paths, context):
            return None
        return _match(ASK, "medium", "AGV2-A004", "Broad or unverifiable staging requires user approval.")
    if _starts(tokens, "git", "commit"):
        return None if is_feature_branch(context.branch) else _match(ASK, "medium", "AGV2-A001", "Commits are auto-approved only on feature branches.")
    if _starts(tokens, "git", "fetch"):
        return None
    if _starts(tokens, "git", "pull"):
        if "--ff-only" in tokens and context.branch not in PROTECTED_BRANCHES and context.working_tree_clean:
            return None
        return _match(ASK, "medium", "AGV2-A001", "Pull requires --ff-only, a clean tree, and a non-protected branch.")
    if tokens[0] in {"rm", "rmdir", "remove-item", "del", "mv", "move-item", "ren", "rename-item"}:
        return _match(ASK, "high", "AGV2-A004", "File removal, movement, or rename requires user approval.")
    if any(word in text for word in ("deploy", "release", "production", "create tag", "delete tag")):
        return _match(ASK, "high", "AGV2-A005", "Deployment, release, or production actions require approval.")
    return None


def _safe_rule(tokens: tuple[str, ...], context: EvaluationContext) -> RuleMatch | None:
    if _safe_controlled_file_write(tokens, context):
        return _match(ALLOW, "low", "AGV2-S004", "New allowlisted text file in the controlled execution sandbox.")
    if _safe_controlled_python(tokens, context):
        return _match(ALLOW, "low", "AGV2-S004", "Workspace-contained controlled execution script is safe.")
    if _is_read_only(tokens):
        return _match(ALLOW, "low", "AGV2-S001", "Read-only repository inspection is safe.")
    if _is_test(tokens):
        return _match(ALLOW, "low", "AGV2-S002", "Test or static verification command is safe.")
    if _starts(tokens, "python", "-m", "afde.cli") and len(tokens) >= 4 and tokens[3] in {"env-check", "providers", "run-mock"}:
        return _match(ALLOW, "low", "AGV2-S002", "Approved AFDE validation command is safe.")
    if _safe_git_mutation(tokens, context):
        return _match(ALLOW, "low", "AGV2-S003", "Verified feature-branch Git workflow is safe.")
    return None


def _safe_controlled_file_write(tokens: tuple[str, ...], context: EvaluationContext) -> bool:
    if len(tokens) != 2 or tokens[0] != "afde-controlled-file-write":
        return False
    candidate = Path(tokens[1])
    if candidate.is_absolute() or candidate.suffix.lower() not in {".py", ".md", ".txt", ".json", ".yaml", ".yml"}:
        return False
    target = (context.repository_root / candidate).resolve()
    sandbox = (context.repository_root / "controlled_execution").resolve()
    return path_is_inside_repository(str(target), context) and _path_inside(target, sandbox) and not target.exists()


def _safe_controlled_python(tokens: tuple[str, ...], context: EvaluationContext) -> bool:
    if len(tokens) != 2 or tokens[0] != "python" or not tokens[1].lower().endswith(".py"):
        return False
    candidate = Path(tokens[1])
    if candidate.is_absolute():
        return False
    target = (context.repository_root / candidate).resolve()
    sandbox = (context.repository_root / "controlled_execution").resolve()
    return target.is_file() and _path_inside(target, sandbox)


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_git_mutation(tokens: tuple[str, ...], context: EvaluationContext) -> bool:
    if _creates_feature_branch(tokens) or _starts(tokens, "git", "fetch"):
        return True
    if _starts(tokens, "git", "commit"):
        return is_feature_branch(context.branch)
    if _starts(tokens, "git", "add"):
        paths = [token for token in tokens[2:] if not token.startswith("-")]
        return _safe_staging_paths(paths, context)
    if _starts(tokens, "git", "push"):
        target = _git_push_target(tokens)
        return bool(target and target.startswith("feature/") and is_feature_branch(context.branch))
    return False


def _is_read_only(tokens: tuple[str, ...]) -> bool:
    if not tokens:
        return False
    if tokens[0] in {"pwd", "ls", "dir", "tree", "find", "cat", "type", "head", "tail", "rg", "grep", "get-childitem", "get-content"}:
        return True
    if _starts(tokens, "git") and len(tokens) >= 2 and tokens[1] in {"status", "diff", "log", "show", "rev-parse"}:
        return True
    if _starts(tokens, "git", "branch", "--show-current"):
        return True
    if tokens in {("python", "--version"), ("python.exe", "--version"), ("pip", "--version")}:
        return True
    return False


def _is_test(tokens: tuple[str, ...]) -> bool:
    return (
        tokens[0] == "pytest"
        or _starts(tokens, "python", "-m", "pytest")
        or _starts(tokens, "ruff", "check")
        or _starts(tokens, "black", "--check")
        or tokens[0] == "mypy"
    )


def _is_write_or_git_mutation(tokens: tuple[str, ...]) -> bool:
    if _starts(tokens, "git") and not _is_read_only(tokens):
        return True
    return bool(tokens and tokens[0] in {"rm", "rmdir", "remove-item", "mv", "move-item", "cp", "copy-item"})


def _creates_feature_branch(tokens: tuple[str, ...]) -> bool:
    if _starts(tokens, "git", "switch", "-c") and len(tokens) > 3:
        return tokens[3].startswith("feature/")
    if _starts(tokens, "git", "checkout", "-b") and len(tokens) > 3:
        return tokens[3].startswith("feature/")
    return False


def _git_push_target(tokens: tuple[str, ...]) -> str | None:
    values = [token for token in tokens[2:] if not token.startswith("-")]
    if len(values) >= 2:
        return values[1].split(":")[-1]
    return None


def _deletes_protected_remote_ref(tokens: tuple[str, ...]) -> bool:
    target = _git_push_target(tokens)
    if "--delete" in tokens and target in PROTECTED_BRANCHES:
        return True
    return any(token.startswith(":") and token[1:] in PROTECTED_BRANCHES for token in tokens[2:])


def _safe_staging_paths(paths: list[str], context: EvaluationContext) -> bool:
    broad = {".", "..", "*", ":/"}
    return bool(paths) and not any(path in broad for path in paths) and all(
        path_is_inside_repository(path, context) for path in paths
    )


def _destructive_filesystem_target(tokens: tuple[str, ...]) -> bool:
    recursive = any("r" in token for token in tokens[1:] if token.startswith("-")) or "-recurse" in tokens
    targets = {token.rstrip("/\\").lower() or "/" for token in tokens[1:] if not token.startswith("-")}
    return recursive and bool(targets & {"/", "~", ".", "c:", "c:\\", "$home"})


def _credential_exfiltration(text: str) -> bool:
    sensitive = re.search(r"(?:\.env|api[_-]?key|token|credential|password|private[_-]?key)", text)
    transfer = re.search(r"(?:curl|wget|invoke-webrequest|scp|ftp|http://|https://)", text)
    return bool(sensitive and transfer)


def _reads_sensitive_file(tokens: tuple[str, ...]) -> bool:
    if not tokens or tokens[0] not in {"cat", "type", "head", "tail", "get-content"}:
        return False
    sensitive_suffixes = (".env", ".pem", ".key", "credentials.json")
    return any(token.endswith(sensitive_suffixes) for token in tokens[1:])


def _starts(tokens: tuple[str, ...], *prefix: str) -> bool:
    return tokens[: len(prefix)] == prefix


def _match(decision: ApprovalDecision, risk: str, rule_id: str, reason: str) -> RuleMatch:
    return RuleMatch(decision, risk, rule_id, reason)
