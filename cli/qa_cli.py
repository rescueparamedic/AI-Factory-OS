from __future__ import annotations


def register_qa_commands(subparsers):
    qa_parser = subparsers.add_parser("qa", help="QA Engine")
    qa_subparsers = qa_parser.add_subparsers(dest="qa_command")
    run_parser = qa_subparsers.add_parser("run", help="최신 또는 지정 Development Run 검수")
    run_parser.add_argument("--dev-run", default=None, help="DEV-ID. 생략 시 최신 Development Run 사용")
    qa_subparsers.add_parser("latest", help="최신 QA 결과 보기")
    list_parser = qa_subparsers.add_parser("list", help="QA 결과 목록")
    list_parser.add_argument("--limit", type=int, default=10, help="표시 개수")


def _print_qa_result(result: dict) -> None:
    print("\n=== QA Engine Result ===")
    print(f"status       : {result['status']}")
    print(f"qa_id        : {result['qa_id']}")
    print(f"dev_run_id   : {result.get('dev_run_id', '')}")
    print(f"plan_id      : {result.get('plan_id', '')}")
    print(f"score        : {result.get('score', '')}")
    print(f"grade        : {result.get('grade', '')}")
    print(f"decision     : {result.get('decision', '')}")
    print(f"checks       : {len(result.get('checks', []))}")
    print(f"qa_path      : {result.get('qa_path', '')}")
    print(f"report_path  : {result.get('report_path', '')}")
    print("\nChecks")
    for check in result.get("checks", []): print(f"- [{check['status']}] {check['name']} : {check['message']}")
    if result.get("recommendations"):
        print("\nRecommendations")
        for item in result["recommendations"]: print(f"- {item}")


def handle_qa_command(kernel, args) -> None:
    if args.qa_command == "run": _print_qa_result(kernel.run_qa_engine(dev_run_id=args.dev_run)); return
    if args.qa_command == "latest": _print_qa_result(kernel.get_latest_qa_result()); return
    if args.qa_command == "list":
        items = kernel.list_qa_results(limit=args.limit)
        print("\n=== QA Result 목록 ===")
        if not items: print("QA 결과가 없습니다."); return
        for item in items: print(f"{item['qa_id']} | {item['dev_run_id']} | {item['score']} | {item['decision']} | {item['created_at']}")
        return
    print("qa 하위 명령어가 필요합니다.")
