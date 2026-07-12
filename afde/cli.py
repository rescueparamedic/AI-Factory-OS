# -*- coding: utf-8 -*-
"""AFDE CLI."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from approval_guardian import ApprovalGuardian, ApprovalRequest
from sprint_auto_runner import SprintAutoRunner
from real_worker_runtime import RealWorkerRuntime
from real_worker_runtime.openai_probe import OpenAIResponsesProbe
from real_worker_runtime.raw_openai_probe import RawOpenAIResponsesProbe
from real_worker_runtime.http_boundary_probe import HTTPBoundaryDiagnostic
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


def _runner_summary(run):
    current = None
    if 0 <= run.current_step_index < len(run.step_results):
        current = asdict(run.step_results[run.current_step_index])
    return {
        "run_id": run.run_id,
        "sprint_id": run.sprint_id,
        "status": run.status,
        "branch": run.branch,
        "current_step_index": run.current_step_index,
        "current_step": current,
        "last_error": run.last_error,
        "pending_approval": run.pending_approval,
        "completed_at": run.completed_at,
    }


def _print_runner(data, json_output=False):
    if json_output:
        _print_json(data)
        return
    print("\n=== Sprint Auto Runner ===")
    for key in ("run_id", "sprint_id", "status", "branch", "current_step_index", "last_error"):
        if key in data:
            print(f"{key:20}: {data.get(key, '')}")
    if data.get("pending_approval"):
        pending = data["pending_approval"]
        print("\nApproval required")
        for key in ("step_id", "redacted_command", "rule_id", "reason"):
            print(f"{key:20}: {pending.get(key, '')}")


def cmd_sprint_validate(args):
    definition = SprintAutoRunner(Path.cwd()).validate(args.file)
    result = {
        "status": "valid",
        "sprint_id": definition.sprint_id,
        "title": definition.title,
        "version": definition.version,
        "steps": len(definition.steps),
        "fingerprint": definition.fingerprint,
    }
    _print_runner(result, args.json)


def cmd_sprint_run(args):
    runner = SprintAutoRunner(Path.cwd())
    if args.dry_run:
        result = runner.dry_run(args.file)
        _print_json(result) if args.json else _print_runner({"status": "dry_run", **result})
        if not args.json:
            for step in result["steps"]:
                print(f"- {step['step_id']} | {step['decision']} | {step['rule_id']} | {step['reason']}")
        return
    _print_runner(_runner_summary(runner.start(args.file)), args.json)


def cmd_sprint_status(args):
    _print_runner(_runner_summary(SprintAutoRunner(Path.cwd()).status(args.run_id)), args.json)


def cmd_sprint_resume(args):
    run = SprintAutoRunner(Path.cwd()).resume(
        args.run_id,
        {
            "step_id": args.approve_step,
            "decision": "approved",
            "approved_by": args.approved_by,
            "reason": args.reason,
        },
    )
    _print_runner(_runner_summary(run), args.json)


def cmd_sprint_cancel(args):
    run = SprintAutoRunner(Path.cwd()).cancel(args.run_id, actor=args.actor)
    _print_runner(_runner_summary(run), args.json)

def cmd_factory_demo(args):
    session=RealWorkerRuntime(Path.cwd()).run(args.request,args.provider,not args.no_live,args.include_approval_demo,args.max_revisions,args.model,args.allow_live_api,enable_controlled_execution=args.enable_controlled_execution)
    data=session.to_dict()
    if args.json: _print_json(data)
    else:
        print("\n=== Demo Complete ===")
        print(f"Session ID : {session.session_id}\nStatus     : {session.status}\nMessages   : {len(session.messages)}\nProgress   : {session.progress}%")
        print("Artifacts:")
        for item in session.artifacts: print(f"- {item['type']}: {item['path']}")

def cmd_openai_probe(args):
    probe=OpenAIResponsesProbe(model=args.model,allow_live_api=args.allow_live_api)
    result=probe.run_many() if args.probe=="all" else probe.run(args.probe)
    _print_json(result)

def cmd_openai_raw_probe(args):
    result=RawOpenAIResponsesProbe(model=args.model,allow_live_api=args.allow_live_api,timeout_seconds=args.timeout).run()
    _print_json(result)

def cmd_openai_http_boundary(args):
    result=HTTPBoundaryDiagnostic(model=args.model,include_post=args.include_post,include_curl_post=args.include_curl_post,include_curl_error_details=args.include_curl_error_details,allow_live_api=args.allow_live_api,timeout_seconds=args.timeout).run()
    _print_json(result)

def cmd_runtime_status(args): _print_json(RealWorkerRuntime(Path.cwd()).status(args.session_id))
def cmd_runtime_report(args): print(RealWorkerRuntime(Path.cwd()).report(args.session_id))
def cmd_runtime_cancel(args): _print_json(RealWorkerRuntime(Path.cwd()).cancel(args.session_id))


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

    p = sub.add_parser("sprint-validate", help="Validate a Sprint Auto Runner JSON definition")
    p.add_argument("--file", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sprint_validate)

    p = sub.add_parser("sprint-run", help="Run an approval-guarded Sprint definition")
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sprint_run)

    p = sub.add_parser("sprint-status", help="Show persisted Sprint run state")
    p.add_argument("--run-id", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sprint_status)

    p = sub.add_parser("sprint-resume", help="Resume the currently waiting Sprint step")
    p.add_argument("--run-id", required=True)
    p.add_argument("--approve-step", required=True)
    p.add_argument("--approved-by", default="user")
    p.add_argument("--reason", default="Approved by user")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sprint_resume)

    p = sub.add_parser("sprint-cancel", help="Cancel a non-terminal Sprint run")
    p.add_argument("--run-id", required=True)
    p.add_argument("--actor", default="user")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sprint_cancel)

    p=sub.add_parser("factory-demo",help="Run the Real AI Worker Runtime demo")
    p.add_argument("--request",required=True); p.add_argument("--provider",default="mock",choices=["mock","openai","gemini"]); p.add_argument("--model"); p.add_argument("--allow-live-api",action="store_true",help="Explicitly allow paid external API calls"); p.add_argument("--enable-controlled-execution",action="store_true",help="Enable bounded approved local execution proposals"); p.add_argument("--json",action="store_true"); p.add_argument("--no-live",action="store_true"); p.add_argument("--include-approval-demo",action="store_true"); p.add_argument("--max-revisions",type=int,default=1,choices=range(0,4)); p.set_defaults(func=cmd_factory_demo)
    p=sub.add_parser("openai-probe",help="Run a minimal opt-in OpenAI Responses API probe")
    p.add_argument("--probe",required=True,choices=["A","B","C","all"]); p.add_argument("--model"); p.add_argument("--allow-live-api",action="store_true",help="Explicitly allow one or more paid probe calls"); p.set_defaults(func=cmd_openai_probe)
    p=sub.add_parser("openai-raw-probe",help="Run an SDK-free opt-in raw HTTPS Responses probe")
    p.add_argument("--model",required=True); p.add_argument("--timeout",type=float,default=60.0); p.add_argument("--allow-live-api",action="store_true",help="Explicitly allow one paid raw HTTPS call"); p.set_defaults(func=cmd_openai_raw_probe)
    p=sub.add_parser("openai-http-boundary",help="Diagnose DNS, TLS, HEAD clients, and optional one-time POST")
    p.add_argument("--model",default="gpt-4.1-mini"); p.add_argument("--timeout",type=float,default=15.0); p.add_argument("--include-post",action="store_true"); p.add_argument("--include-curl-post",action="store_true",help="Include one minimal curl.exe POST (also requires --allow-live-api)"); p.add_argument("--include-curl-error-details",action="store_true",help="Allowlist JSON error fields from the curl POST response"); p.add_argument("--allow-live-api",action="store_true",help="Required with either POST option"); p.set_defaults(func=cmd_openai_http_boundary)
    p=sub.add_parser("runtime-status"); p.add_argument("--session-id",required=True); p.set_defaults(func=cmd_runtime_status)
    p=sub.add_parser("runtime-report"); p.add_argument("--session-id",required=True); p.set_defaults(func=cmd_runtime_report)
    p=sub.add_parser("runtime-cancel"); p.add_argument("--session-id",required=True); p.set_defaults(func=cmd_runtime_cancel)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
