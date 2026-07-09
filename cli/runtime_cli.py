from __future__ import annotations


def register_runtime_commands(subparsers):
    runtime_parser = subparsers.add_parser("runtime", help="Worker Runtime Engine")
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_command")

    runtime_subparsers.add_parser("worker-list", help="Runtime Worker 목록")
    runtime_subparsers.add_parser("providers", help="AI Provider 설정 상태 확인")

    run_parser = runtime_subparsers.add_parser("run", help="Runtime Worker 실행")
    run_parser.add_argument("--worker", required=True, help="worker_id")
    run_parser.add_argument("--task", required=True, help="실행할 작업")
    run_parser.add_argument("--product", default="blog_growth_analyzer", help="Product ID")

    runtime_subparsers.add_parser("latest", help="최신 Runtime 실행 결과")

    list_parser = runtime_subparsers.add_parser("list", help="Runtime 실행 목록")
    list_parser.add_argument("--limit", type=int, default=10)


def _print_runtime(result):
    print("\n=== Worker Runtime Result ===")
    for key in ["status", "run_id", "worker_id", "worker_name", "product_id", "task", "mode", "artifact_path", "report_path", "run_path", "next_stage"]:
        print(f"{key:14}: {result.get(key, '')}")

    provider = result.get("provider") or {}
    if provider:
        print("\nProvider")
        print(f"provider_id  : {provider.get('provider_id', '')}")
        print(f"name         : {provider.get('name', '')}")
        print(f"mode         : {provider.get('mode', '')}")
        print(f"status       : {provider.get('status', '')}")

    print("\nSteps")
    for step in result.get("steps", []):
        print(f"- [{step.get('status')}] {step.get('step')} : {step.get('message')}")


def handle_runtime_command(kernel, args):
    try:
        if args.runtime_command == "worker-list":
            workers = kernel.list_runtime_workers()
            print("\n=== Runtime Worker 목록 ===")
            for worker in workers:
                print(f"{worker.get('worker_id')} | {worker.get('name')} | {worker.get('status')} | {worker.get('capability')}")
            return

        if args.runtime_command == "providers":
            providers = kernel.list_ai_providers()
            print("\n=== AI Provider 상태 ===")
            for provider in providers:
                print(f"{provider.get('provider_id')} | {provider.get('name')} | {provider.get('status')} | env:{provider.get('env_key')} | mode:{provider.get('mode')}")
            return

        if args.runtime_command == "run":
            result = kernel.run_runtime_worker(worker_id=args.worker, task=args.task, product_id=args.product)
            _print_runtime(result)
            return

        if args.runtime_command == "latest":
            _print_runtime(kernel.get_latest_runtime_run())
            return

        if args.runtime_command == "list":
            items = kernel.list_runtime_runs(limit=args.limit)
            print("\n=== Runtime Run 목록 ===")
            if not items:
                print("Runtime 실행 결과가 없습니다.")
                print("\nSuggested command")
                print('python "C:\\AIFactory\\AI Factory OS\\main.py" runtime worker-list')
                print('python "C:\\AIFactory\\AI Factory OS\\main.py" runtime run --worker python_worker --task "테스트 작업"')
                return
            for item in items:
                print(f"{item.get('run_id')} | {item.get('worker_id')} | {item.get('status')} | {item.get('mode')} | {item.get('task')} | {item.get('created_at')}")
            return

        print("runtime 하위 명령어가 필요합니다.")
    except FileNotFoundError:
        print("\n=== Worker Runtime 안내 ===")
        print("No runtime run found.")
        print("\nSuggested command")
        print('python "C:\\AIFactory\\AI Factory OS\\main.py" runtime run --worker python_worker --task "테스트 작업"')
    except ValueError as exc:
        print("\n=== Worker Runtime 오류 ===")
        print(str(exc))
        print("\nSuggested command")
        print('python "C:\\AIFactory\\AI Factory OS\\main.py" runtime worker-list')
