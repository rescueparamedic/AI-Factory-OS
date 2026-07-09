from __future__ import annotations


def register_pipeline_commands(subparsers):
    pipeline_parser = subparsers.add_parser("pipeline", help="AI Factory 자동 개발 파이프라인")
    pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_command")

    run_parser = pipeline_subparsers.add_parser("run", help="요청 → 계획 → 개발 → QA → 문서화 → 승인대기 생성")
    run_parser.add_argument("--request", required=True, help="사용자 개발 요청")
    run_parser.add_argument("--product", default="blog_growth_analyzer", help="대상 Product ID")

    pipeline_subparsers.add_parser("latest", help="최신 Pipeline 실행 결과 보기")

    list_parser = pipeline_subparsers.add_parser("list", help="Pipeline 실행 목록")
    list_parser.add_argument("--limit", type=int, default=10, help="표시 개수")


def _print_pipeline_result(result: dict) -> None:
    print("\n=== Pipeline Orchestrator Result ===")
    print(f"status       : {result.get('status', '')}")
    print(f"pipeline_id  : {result.get('pipeline_id', '')}")
    print(f"product_id   : {result.get('product_id', '')}")
    print(f"request      : {result.get('request', '')}")
    print(f"plan_id      : {result.get('plan_id', '')}")
    print(f"dev_run_id   : {result.get('dev_run_id', '')}")
    print(f"qa_id        : {result.get('qa_id', '')}")
    print(f"doc_id       : {result.get('doc_id', '')}")
    print(f"approval_id  : {result.get('approval_id', '')}")
    print(f"qa_decision  : {result.get('qa_decision', '')}")
    print(f"qa_score     : {result.get('qa_score', '')}")
    print(f"next_stage   : {result.get('next_stage', '')}")
    print(f"pipeline_path: {result.get('pipeline_path', '')}")
    print(f"report_path  : {result.get('report_path', '')}")

    print("\nSteps")
    for step in result.get("steps", []):
        print(f"- [{step.get('status')}] {step.get('name')} : {step.get('id', '')}")


def handle_pipeline_command(kernel, args) -> None:
    if args.pipeline_command == "run":
        result = kernel.run_pipeline(request=args.request, product_id=args.product)
        _print_pipeline_result(result)
        return

    if args.pipeline_command == "latest":
        result = kernel.get_latest_pipeline_result()
        _print_pipeline_result(result)
        return

    if args.pipeline_command == "list":
        items = kernel.list_pipeline_results(limit=args.limit)
        print("\n=== Pipeline Result 목록 ===")
        if not items:
            print("Pipeline 실행 결과가 없습니다.")
            return
        for item in items:
            print(f"{item.get('pipeline_id')} | {item.get('status')} | {item.get('approval_id')} | {item.get('created_at')}")
        return

    print("pipeline 하위 명령어가 필요합니다.")
