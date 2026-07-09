from __future__ import annotations


def register_product_commands(subparsers):
    product_parser = subparsers.add_parser("product", help="Product 개발 파이프라인")
    product_subparsers = product_parser.add_subparsers(dest="product_command")

    product_subparsers.add_parser("list", help="Product 목록 보기")

    run_parser = product_subparsers.add_parser("run-dev", help="Product 개발 파이프라인 실행")
    run_parser.add_argument("--product", default="blog_growth_analyzer", help="Product ID")
    run_parser.add_argument("--title", default="Blog Growth Analyzer MVP Task", help="개발 Task 제목")
    run_parser.add_argument("--request", default="Create product development pipeline report", help="개발 요청 내용")

    product_subparsers.add_parser("status", help="Product 상태 보기")


def handle_product_command(kernel, args) -> None:
    if args.product_command == "list":
        products = kernel.list_products()
        print("\n=== Product 목록 ===")
        for product in products:
            print(f"{product['product_id']} | {product['product_name']} | {product['status']} | {product['version']}")
        return

    if args.product_command == "run-dev":
        result = kernel.run_product_development(
            product_id=args.product,
            title=args.title,
            request=args.request,
        )
        print("\n=== Product Development Pipeline ===")
        print(f"status          : {result['status']}")
        print(f"product_id      : {result['product_id']}")
        print(f"task_id         : {result['task_id']}")
        print(f"pipeline_id     : {result['pipeline_id']}")
        print(f"ceo_decision    : {result['ceo_decision']}")
        print(f"pm_plan         : {result['pm_plan']}")
        print(f"dev_result      : {result['dev_result']}")
        print(f"qa_status       : {result['qa_status']}")
        print(f"report_path     : {result['report_path']}")
        print(f"audit_path      : {result['audit_path']}")
        return

    if args.product_command == "status":
        status = kernel.get_product_pipeline_status()
        print("\n=== Product Pipeline Status ===")
        print(f"pipelines : {status['pipeline_count']}")
        print(f"latest    : {status.get('latest_pipeline_id', '')}")
        print(f"reports   : {status['report_count']}")
        return

    print("product 하위 명령어가 필요합니다.")
