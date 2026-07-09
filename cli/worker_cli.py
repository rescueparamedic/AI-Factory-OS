from __future__ import annotations


def register_worker_commands(subparsers):
    worker_parser = subparsers.add_parser("worker", help="Worker 관리")
    worker_subparsers = worker_parser.add_subparsers(dest="worker_command")
    worker_subparsers.add_parser("list", help="등록된 Worker 목록")
    worker_subparsers.add_parser("run-test", help="Worker 표준 결과 테스트 실행")


def handle_worker_command(kernel, args) -> None:
    if args.worker_command == "list":
        print("\n=== Worker 목록 ===")
        for worker in kernel.list_workers():
            print(
                f"{worker['worker_id']} | {worker['role']} | "
                f"permission:{worker['permission_level']} | approval:{worker['requires_approval']}"
            )
        return

    if args.worker_command == "run-test":
        result = kernel.run_worker_standard_test()
        print("\n=== Worker 표준 결과 테스트 ===")
        print(f"status      : {result['status']}")
        print(f"worker_id   : {result['worker_id']}")
        print(f"result_id   : {result['result_id']}")
        print(f"saved_path  : {result['saved_path']}")
        return

    print("worker 하위 명령어가 필요합니다.")
