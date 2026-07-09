from __future__ import annotations


def register_doctor_commands(subparsers):
    subparsers.add_parser("doctor", help="프로젝트 상태 진단")


def handle_doctor_command(kernel, args) -> None:
    report = kernel.run_doctor()
    print("\n=== AI Factory OS Project Doctor ===")
    print(f"project_path : {report['project_path']}")
    print(f"health       : {report['health_score']}%")
    print(f"status       : {report['status']}")
    print("\nChecks")
    for check in report["checks"]:
        print(f"- [{check['status']}] {check['name']} : {check['message']}")
    if report["warnings"]:
        print("\nWarnings")
        for warning in report["warnings"]:
            print(f"- {warning}")
    print(f"\nreport_path  : {report['report_path']}")
