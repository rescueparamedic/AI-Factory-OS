from __future__ import annotations


def register_task_commands(subparsers):
    task_parser = subparsers.add_parser("task", help="Task 관리")
    task_subparsers = task_parser.add_subparsers(dest="task_command")

    create_parser = task_subparsers.add_parser("create", help="새 Task 생성")
    create_parser.add_argument("--title", default="Manual Task", help="Task 제목")
    create_parser.add_argument("--description", default="Created from CLI", help="Task 설명")
    create_parser.add_argument("--product", default="blog_growth_analyzer", help="Product ID")
    create_parser.add_argument("--worker", default="markdown_worker", help="담당 Worker")

    list_parser = task_subparsers.add_parser("list", help="Task 목록 보기")
    list_parser.add_argument("--limit", type=int, default=20, help="표시 개수")

    show_parser = task_subparsers.add_parser("show", help="Task 상세 보기")
    show_parser.add_argument("task_id", help="Task ID")

    update_task_parser = task_subparsers.add_parser("update", help="Task 상태 변경")
    update_task_parser.add_argument("task_id", help="Task ID")
    update_task_parser.add_argument("status", help="변경할 상태")

    run_parser = task_subparsers.add_parser("run-next", help="Task를 다음 Workflow 상태로 이동")
    run_parser.add_argument("task_id", help="Task ID")


def handle_task_command(kernel, args) -> None:
    if args.task_command == "create":
        task = kernel.create_manual_task(
            title=args.title,
            description=args.description,
            product_id=args.product,
            assigned_worker=args.worker,
        )
        print("\nTask 생성 완료")
        print(f"Task ID : {task['task_id']}")
        print(f"Status  : {task['status']}")
        print(f"Path    : data/tasks/{task['task_id']}.json")
        return

    if args.task_command == "list":
        tasks = kernel.list_tasks(limit=args.limit)
        print("\n=== Task 목록 ===")
        if not tasks:
            print("생성된 Task가 없습니다.")
            return
        for task in tasks:
            print(f"{task['task_id']} | {task['status']} | {task['title']}")
        return

    if args.task_command == "show":
        task = kernel.get_task(args.task_id)
        print("\n=== Task 상세 ===")
        print(f"Task ID      : {task['task_id']}")
        print(f"Title        : {task['title']}")
        print(f"Product      : {task['product_id']}")
        print(f"Worker       : {task['assigned_worker']}")
        print(f"Status       : {task['status']}")
        print(f"Created at   : {task['created_at']}")
        print(f"Updated at   : {task['updated_at']}")
        print("\nHistory")
        for item in task.get("history", []):
            print(f"- {item['timestamp']} | {item['status']} | {item.get('note', '')}")
        return

    if args.task_command == "update":
        task = kernel.update_task_status(args.task_id, args.status)
        print("\nTask 상태 변경 완료")
        print(f"Task ID : {task['task_id']}")
        print(f"Status  : {task['status']}")
        return

    if args.task_command == "run-next":
        task = kernel.run_task_next(args.task_id)
        print("\nTask 다음 단계 이동 완료")
        print(f"Task ID : {task['task_id']}")
        print(f"Status  : {task['status']}")
        return

    print("task 하위 명령어가 필요합니다.")
