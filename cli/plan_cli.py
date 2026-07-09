from __future__ import annotations


def register_plan_commands(subparsers):
    plan_parser = subparsers.add_parser("plan", help="Planning Engine")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command")

    create_parser = plan_subparsers.add_parser("create", help="자연어 요청을 개발 계획으로 변환")
    create_parser.add_argument("--request", required=True, help="사용자 개발 요청")
    create_parser.add_argument("--product", default="blog_growth_analyzer", help="대상 Product ID")

    list_parser = plan_subparsers.add_parser("list", help="생성된 개발 계획 목록")
    list_parser.add_argument("--limit", type=int, default=10, help="표시 개수")

    show_parser = plan_subparsers.add_parser("show", help="개발 계획 상세 보기. PLAN-ID 생략 시 최신 계획 표시")
    show_parser.add_argument("plan_id", nargs="?", default=None, help="PLAN-ID")

    plan_subparsers.add_parser("latest", help="최신 개발 계획 상세 보기")


def _print_plan_detail(plan: dict) -> None:
    print("\n=== Development Plan 상세 ===")
    print(f"plan_id     : {plan['plan_id']}")
    print(f"product_id  : {plan['product_id']}")
    print(f"request     : {plan['request']}")
    print(f"priority    : {plan['priority']}")
    print(f"risk_level  : {plan['risk_level']}")
    print(f"approval    : {plan['approval_required']}")
    print(f"difficulty  : {plan.get('difficulty', '')}")
    print(f"estimated   : {plan.get('estimated_total_time', '')}")
    print(f"regression  : {plan.get('regression_required', '')}")
    print(f"handoff     : {plan.get('handoff_path', '')}")

    print("\nRequirements")
    for req in plan.get("requirements", []):
        print(f"- {req}")

    print("\nExpected Files")
    for file in plan.get("expected_files", []):
        print(f"- {file}")

    print("\nTasks")
    for task in plan.get("tasks", []):
        print(f"- {task['task_id']} | {task['title']} | {task['owner_agent']} | {task['estimated_effort']}")

    print("\nRisks")
    for risk in plan.get("risks", []):
        print(f"- [{risk['level']}] {risk['risk']} -> {risk['mitigation']}")


def handle_plan_command(kernel, args) -> None:
    if args.plan_command == "create":
        result = kernel.create_development_plan(
            request=args.request,
            product_id=args.product,
        )
        print("\n=== Planning Engine Result ===")
        print(f"status       : {result['status']}")
        print(f"plan_id      : {result['plan_id']}")
        print(f"product_id   : {result['product_id']}")
        print(f"priority     : {result['priority']}")
        print(f"risk_level   : {result['risk_level']}")
        print(f"difficulty   : {result.get('difficulty', '')}")
        print(f"estimated    : {result.get('estimated_total_time', '')}")
        print(f"regression   : {result.get('regression_required', '')}")
        print(f"approval     : {result['approval_required']}")
        print(f"task_count   : {len(result['tasks'])}")
        print(f"plan_path    : {result['plan_path']}")
        print(f"report_path  : {result['report_path']}")
        print(f"handoff_path : {result.get('handoff_path', '')}")

        print("\nExpected Files")
        for file in result.get("expected_files", []):
            print(f"- {file}")

        print("\nTasks")
        for task in result["tasks"]:
            print(f"- {task['task_id']} | {task['title']} | {task['owner_agent']} | {task['status']}")
        return

    if args.plan_command == "list":
        plans = kernel.list_development_plans(limit=args.limit)
        print("\n=== Development Plan 목록 ===")
        if not plans:
            print("생성된 개발 계획이 없습니다.")
            return
        for plan in plans:
            print(f"{plan['plan_id']} | {plan['product_id']} | {plan['priority']} | {plan['risk_level']} | {plan['created_at']}")
        return

    if args.plan_command == "show":
        plan = kernel.get_development_plan(args.plan_id)
        _print_plan_detail(plan)
        return

    if args.plan_command == "latest":
        plan = kernel.get_latest_development_plan()
        _print_plan_detail(plan)
        return

    print("plan 하위 명령어가 필요합니다.")
