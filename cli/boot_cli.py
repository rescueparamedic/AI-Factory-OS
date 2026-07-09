from __future__ import annotations


def register_boot_commands(subparsers):
    subparsers.add_parser("boot", help="OS Core boot 실행")


def handle_boot_command(kernel, args) -> None:
    result = kernel.boot()
    print("\n=== AI Factory OS / Sprint 10-1 ===")
    print(f"Boot status      : {result['status']}")
    print(f"Product          : {result['product_name']}")
    print(f"Task ID          : {result['task_id']}")
    print(f"Workflow status  : {result['workflow_status']}")
    print(f"CEO decision     : {result.get('ceo_decision', '')}")
    print(f"PM plan          : {result.get('pm_plan', '')}")
    print(f"Team assigned    : {result.get('team_assigned', '')}")
    print(f"Worker result    : {result.get('worker_result_path', '')}")
    print(f"Audit log        : {result['audit_log_path']}")
    print(f"Project status   : {result['project_status_path']}")
    print("\n실행 완료: data 폴더에서 생성 결과를 확인하세요.")
