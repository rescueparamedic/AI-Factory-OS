from __future__ import annotations

import argparse

from os_core.kernel import AIFactoryKernel
from cli.boot_cli import register_boot_commands, handle_boot_command
from cli.version_cli import register_version_commands, handle_version_command
from cli.doctor_cli import register_doctor_commands, handle_doctor_command
from cli.task_cli import register_task_commands, handle_task_command
from cli.agent_cli import register_agent_commands, handle_agent_command
from cli.worker_cli import register_worker_commands, handle_worker_command
from cli.update_cli import register_update_commands, handle_update_command
from cli.product_cli import register_product_commands, handle_product_command
from cli.repo_cli import register_repo_commands, handle_repo_command
from cli.plan_cli import register_plan_commands, handle_plan_command
from cli.dev_cli import register_dev_commands, handle_dev_command
from cli.package_cli import register_package_commands, handle_package_command
from cli.qa_cli import register_qa_commands, handle_qa_command
from cli.docs_cli import register_docs_commands, handle_docs_command
from cli.approval_cli import register_approval_commands, handle_approval_command
from cli.pipeline_cli import register_pipeline_commands, handle_pipeline_command
from cli.release_cli import register_release_commands, handle_release_command
from cli.deploy_cli import register_deploy_commands, handle_deploy_command
from cli.runtime_cli import register_runtime_commands, handle_runtime_command
from cli.chat_cli import register_chat_commands, handle_chat_command
from cli.dashboard_cli import register_dashboard_commands, handle_dashboard_command
from cli.ai_cli import register_ai_commands, handle_ai_command
from cli.scheduler_cli import register_scheduler_commands, handle_scheduler_command

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="AI Factory OS", description="AI Factory OS v2.5 Real AI Worker CLI")
    subparsers = parser.add_subparsers(dest="command")
    register_boot_commands(subparsers); register_version_commands(subparsers); register_doctor_commands(subparsers)
    register_task_commands(subparsers); register_agent_commands(subparsers); register_worker_commands(subparsers)
    register_update_commands(subparsers); register_product_commands(subparsers); register_repo_commands(subparsers)
    register_plan_commands(subparsers); register_dev_commands(subparsers); register_package_commands(subparsers)
    register_qa_commands(subparsers); register_docs_commands(subparsers); register_approval_commands(subparsers)
    register_pipeline_commands(subparsers); register_release_commands(subparsers); register_deploy_commands(subparsers)
    register_runtime_commands(subparsers); register_chat_commands(subparsers); register_dashboard_commands(subparsers); register_ai_commands(subparsers); register_scheduler_commands(subparsers)
    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    kernel = AIFactoryKernel()
    handlers = {
        None: handle_boot_command, "boot": handle_boot_command, "version": handle_version_command,
        "doctor": handle_doctor_command, "task": handle_task_command, "agent": handle_agent_command,
        "worker": handle_worker_command, "update": handle_update_command, "product": handle_product_command,
        "repo": handle_repo_command, "plan": handle_plan_command, "dev": handle_dev_command,
        "package": handle_package_command, "qa": handle_qa_command, "docs": handle_docs_command,
        "approve": handle_approval_command, "pipeline": handle_pipeline_command, "release": handle_release_command,
        "deploy": handle_deploy_command, "runtime": handle_runtime_command, "chat": handle_chat_command,
        "dashboard": handle_dashboard_command, "ai": handle_ai_command, "scheduler": handle_scheduler_command,
    }
    handler = handlers.get(args.command)
    if handler:
        handler(kernel, args)
        return
    parser.print_help()
