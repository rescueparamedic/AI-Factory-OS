from __future__ import annotations

def register_dashboard_commands(subparsers):
    dashboard_parser = subparsers.add_parser("dashboard", help="AI Factory Dashboard")
    dashboard_subparsers = dashboard_parser.add_subparsers(dest="dashboard_command")
    dashboard_subparsers.add_parser("build", help="대시보드 HTML 생성")
    dashboard_subparsers.add_parser("open", help="대시보드 생성 후 브라우저 열기")
    dashboard_subparsers.add_parser("latest", help="최신 대시보드 스냅샷 보기")
    live_build = dashboard_subparsers.add_parser("live-build", help="Live Dashboard HTML 생성")
    live_build.add_argument("--refresh", type=int, default=10)
    live_open = dashboard_subparsers.add_parser("live-open", help="Live Dashboard 생성 후 브라우저 열기")
    live_open.add_argument("--refresh", type=int, default=10)
    dashboard_subparsers.add_parser("status", help="Live Dashboard 상태 확인")

def _print_dashboard(result):
    print("\n=== AI Factory Dashboard ===")
    for key in ["status", "dashboard_id", "live_id", "html_path", "json_path", "refresh_seconds", "created_at", "next_stage"]:
        if key in result:
            print(f"{key:16}: {result.get(key, '')}")

def handle_dashboard_command(kernel, args):
    try:
        if args.dashboard_command == "build":
            _print_dashboard(kernel.build_dashboard())
            return
        if args.dashboard_command == "open":
            result = kernel.open_dashboard()
            _print_dashboard(result)
            print("opened          : True")
            return
        if args.dashboard_command == "latest":
            result = kernel.get_latest_dashboard()
            print("\n=== Latest Dashboard Snapshot ===")
            print(f"dashboard_id : {result.get('dashboard_id', '')}")
            print(f"created_at   : {result.get('created_at', '')}")
            version = result.get("version") or {}
            print(f"version      : {version.get('version', '')}")
            conversation = result.get("latest_conversation") or {}
            print(f"conversation : {conversation.get('conversation_id', 'No data')}")
            runtime = result.get("latest_runtime") or {}
            print(f"runtime      : {runtime.get('run_id', 'No data')}")
            return
        if args.dashboard_command == "live-build":
            _print_dashboard(kernel.build_live_dashboard(refresh_seconds=args.refresh))
            return
        if args.dashboard_command == "live-open":
            result = kernel.open_live_dashboard(refresh_seconds=args.refresh)
            _print_dashboard(result)
            print("opened          : True")
            return
        if args.dashboard_command == "status":
            result = kernel.get_live_dashboard_status()
            print("\n=== Live Dashboard Status ===")
            for key, value in result.items():
                print(f"{key:18}: {value}")
            return
        print("dashboard 하위 명령어가 필요합니다.")
    except FileNotFoundError:
        print("\n=== Dashboard 안내 ===")
        print("No dashboard found.")
        print("\nSuggested command")
        print('python "C:\\AIFactory\\AI Factory OS\\main.py" dashboard build')
