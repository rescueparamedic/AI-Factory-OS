# -*- coding: utf-8 -*-
"""AFDE CLI."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from approval_guardian import ApprovalGuardian, ApprovalRequest
from .environment_checker import EnvironmentChecker
from .provider_manager import ProviderManager
from .real_ai_worker_bootstrap import RealAIWorkerBootstrap
from .task_runner import TaskRunner


def _print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_providers(args):
    _print_json(ProviderManager().as_dicts())


def cmd_git_status(args):
    # lightweight status helper; avoids hard dependency on previous GitManager implementation details
    import subprocess
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    _print_json({"status": "success" if result.returncode == 0 else "failed", "output": result.stdout.strip(), "error": result.stderr.strip()})


def cmd_run_mock(args):
    runner = TaskRunner()
    result = runner.run_mock(title=args.title, request=args.request)
    _print_json(result)


def cmd_env_check(args):
    checker = EnvironmentChecker()
    report = checker.run_all()
    path = checker.save_report()
    report["report_path"] = str(path)
    _print_json(report)


def cmd_bootstrap_worker(args):
    result = RealAIWorkerBootstrap().run()
    _print_json(result)


def cmd_approval_check(args):
    request = ApprovalRequest(
        command=args.exec_command,
        cwd=str(Path.cwd()),
        actor=args.actor,
        task_id=args.task_id,
        branch=args.branch,
        environment=args.environment,
    )
    result = ApprovalGuardian(Path.cwd()).evaluate(request)
    _print_json(asdict(result))


def build_parser():
    parser = argparse.ArgumentParser(prog="afde", description="AI Factory Development Environment CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("providers", help="List AI provider status")
    p.set_defaults(func=cmd_providers)

    p = sub.add_parser("git-status", help="Show git short status")
    p.set_defaults(func=cmd_git_status)

    p = sub.add_parser("run-mock", help="Run AFDE mock pipeline")
    p.add_argument("--title", required=True)
    p.add_argument("--request", required=True)
    p.set_defaults(func=cmd_run_mock)

    p = sub.add_parser("env-check", help="Check local development environment")
    p.set_defaults(func=cmd_env_check)

    p = sub.add_parser("bootstrap-worker", help="Create Real AI Worker bootstrap manifest")
    p.set_defaults(func=cmd_bootstrap_worker)

    p = sub.add_parser("approval-check", help="Classify a command with Approval Guardian v2")
    p.add_argument("--command", dest="exec_command", required=True)
    p.add_argument("--actor", default="afde-cli")
    p.add_argument("--task-id", default=None)
    p.add_argument("--branch", default=None)
    p.add_argument("--environment", default="dev")
    p.set_defaults(func=cmd_approval_check)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
