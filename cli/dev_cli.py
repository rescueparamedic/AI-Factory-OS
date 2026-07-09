from __future__ import annotations


def register_dev_commands(subparsers):
    dev_parser = subparsers.add_parser("dev", help="Development Engine")
    dev_subparsers = dev_parser.add_subparsers(dest="dev_command")

    run_parser = dev_subparsers.add_parser("run", help="개발 계획 handoff 기반 개발 산출물 생성")
    run_parser.add_argument("--plan", default=None, help="PLAN-ID. 생략 시 최신 계획 사용")
    run_parser.add_argument("--apply", action="store_true", help="실제 파일 반영. MVP에서는 안전상 차단됨")

    dev_subparsers.add_parser("latest", help="최신 개발 실행 결과 보기")

    list_parser = dev_subparsers.add_parser("list", help="개발 실행 목록")
    list_parser.add_argument("--limit", type=int, default=10, help="표시 개수")


def _print_dev_result(result: dict) -> None:
    print("\n=== Development Engine Result ===")
    print(f"status       : {result['status']}")
    print(f"run_id       : {result['run_id']}")
    print(f"plan_id      : {result.get('plan_id', '')}")
    print(f"product_id   : {result.get('product_id', '')}")
    print(f"mode         : {result.get('mode', '')}")
    print(f"message      : {result.get('message', '')}")
    print(f"files        : {len(result.get('generated_files', []))}")
    print(f"diff_path    : {result.get('diff_path', '')}")
    print(f"run_path     : {result.get('run_path', '')}")
    print(f"report_path  : {result.get('report_path', '')}")

    if result.get("generated_files"):
        print("\nGenerated Files")
        for item in result.get("generated_files", []):
            print(f"- {item['target_path']} | {item['artifact_path']} | {item['action']}")


def handle_dev_command(kernel, args) -> None:
    if args.dev_command == "run":
        result = kernel.run_development_engine(plan_id=args.plan, apply_changes=args.apply)
        _print_dev_result(result)
        return

    if args.dev_command == "latest":
        result = kernel.get_latest_development_run()
        _print_dev_result(result)
        return

    if args.dev_command == "list":
        runs = kernel.list_development_runs(limit=args.limit)
        print("\n=== Development Run 목록 ===")
        if not runs:
            print("개발 실행 결과가 없습니다.")
            return
        for run in runs:
            print(f"{run['run_id']} | {run['plan_id']} | {run['status']} | {run['created_at']}")
        return

    print("dev 하위 명령어가 필요합니다.")
