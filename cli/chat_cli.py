from __future__ import annotations


def register_chat_commands(subparsers):
    chat_parser = subparsers.add_parser("chat", help="Agent Conversation Engine")
    chat_subparsers = chat_parser.add_subparsers(dest="chat_command")

    run_parser = chat_subparsers.add_parser("run", help="Agent Conversation 실행")
    run_parser.add_argument("--request", required=True, help="개발 요청")
    run_parser.add_argument("--product", default="blog_growth_analyzer", help="Product ID")

    chat_subparsers.add_parser("latest", help="최신 Agent Conversation 보기")

    list_parser = chat_subparsers.add_parser("list", help="Agent Conversation 목록")
    list_parser.add_argument("--limit", type=int, default=10)


def _print_conversation(result: dict) -> None:
    print("\n======================================")
    print("AI Factory Conversation")
    print("======================================")
    print(f"conversation_id : {result.get('conversation_id', '')}")
    print(f"status          : {result.get('status', '')}")
    print(f"product_id      : {result.get('product_id', '')}")
    print(f"plan_id         : {result.get('plan_id', '')}")
    print(f"message_count   : {result.get('message_count', '')}")
    print(f"report_path     : {result.get('report_path', '')}")
    print(f"conversation_path: {result.get('conversation_path', '')}")
    print("\nMessages\n")

    for item in result.get("messages", []):
        print(f"[{item.get('agent')}] {item.get('role')}")
        print(f"- {item.get('message')}")
        print("")


def handle_chat_command(kernel, args):
    try:
        if args.chat_command == "run":
            result = kernel.run_agent_conversation(request=args.request, product_id=args.product)
            _print_conversation(result)
            return

        if args.chat_command == "latest":
            _print_conversation(kernel.get_latest_agent_conversation())
            return

        if args.chat_command == "list":
            items = kernel.list_agent_conversations(limit=args.limit)
            print("\n=== Agent Conversation 목록 ===")
            if not items:
                print("Conversation 결과가 없습니다.")
                print("\nSuggested command")
                print('python "C:\\AIFactory\\AI Factory OS\\main.py" chat run --request "블로그 작성기에 Gemini 검수 기능 추가"')
                return
            for item in items:
                print(f"{item.get('conversation_id')} | {item.get('status')} | {item.get('product_id')} | messages:{item.get('message_count')} | {item.get('request')} | {item.get('created_at')}")
            return

        print("chat 하위 명령어가 필요합니다.")
    except FileNotFoundError:
        print("\n=== Agent Conversation 안내 ===")
        print("No conversation found.")
        print("\nSuggested command")
        print('python "C:\\AIFactory\\AI Factory OS\\main.py" chat run --request "블로그 작성기에 Gemini 검수 기능 추가"')
