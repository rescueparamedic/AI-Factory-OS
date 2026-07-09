from __future__ import annotations

import argparse
import json
from pathlib import Path

from .task_runner import AFDETaskRunner
from .provider_manager import ProviderManager
from .git_manager import GitManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afde", description="AI Factory Development Environment CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-mock", help="Run local safe-mode AFDE mock pipeline")
    run.add_argument("--title", required=True)
    run.add_argument("--request", required=True)

    sub.add_parser("providers", help="Show provider configuration status")
    sub.add_parser("git-status", help="Show git branch and short status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path.cwd()

    if args.command == "run-mock":
        result = AFDETaskRunner(project_root).run_mock_pipeline(args.title, args.request)
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0

    if args.command == "providers":
        print(json.dumps(ProviderManager(project_root).as_dicts(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "git-status":
        git = GitManager(project_root)
        status = git.status()
        print(f"branch: {git.current_branch()}")
        print(status.stdout or status.stderr)
        return status.returncode

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
