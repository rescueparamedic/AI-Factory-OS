from __future__ import annotations


def register_docs_commands(subparsers):
    docs_parser = subparsers.add_parser("docs", help="Documentation Engine")
    docs_subparsers = docs_parser.add_subparsers(dest="docs_command")

    run_parser = docs_subparsers.add_parser("run", help="최신 또는 지정 QA 결과 기반 문서 생성")
    run_parser.add_argument("--qa", default=None, help="QA-ID. 생략 시 최신 QA 결과 사용")

    docs_subparsers.add_parser("latest", help="최신 Documentation 결과 보기")

    list_parser = docs_subparsers.add_parser("list", help="Documentation 결과 목록")
    list_parser.add_argument("--limit", type=int, default=10, help="표시 개수")


def _print_docs_result(result: dict) -> None:
    print("\n=== Documentation Engine Result ===")
    print(f"status       : {result['status']}")
    print(f"doc_id       : {result['doc_id']}")
    print(f"qa_id        : {result.get('qa_id', '')}")
    print(f"dev_run_id   : {result.get('dev_run_id', '')}")
    print(f"plan_id      : {result.get('plan_id', '')}")
    print(f"decision     : {result.get('qa_decision', '')}")
    print(f"score        : {result.get('qa_score', '')}")
    print(f"docs_count   : {len(result.get('documents', []))}")
    print(f"doc_path     : {result.get('doc_path', '')}")

    print("\nDocuments")
    for item in result.get("documents", []):
        print(f"- {item['type']} | {item['path']}")


def handle_docs_command(kernel, args) -> None:
    if args.docs_command == "run":
        result = kernel.run_documentation_engine(qa_id=args.qa)
        _print_docs_result(result)
        return

    if args.docs_command == "latest":
        result = kernel.get_latest_documentation_result()
        _print_docs_result(result)
        return

    if args.docs_command == "list":
        items = kernel.list_documentation_results(limit=args.limit)
        print("\n=== Documentation Result 목록 ===")
        if not items:
            print("Documentation 결과가 없습니다.")
            return
        for item in items:
            print(f"{item['doc_id']} | {item['qa_id']} | {item['status']} | {item['created_at']}")
        return

    print("docs 하위 명령어가 필요합니다.")
