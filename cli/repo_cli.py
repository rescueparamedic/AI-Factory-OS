from __future__ import annotations


def register_repo_commands(subparsers):
    repo_parser = subparsers.add_parser("repo", help="Repository 운영 관리")
    repo_subparsers = repo_parser.add_subparsers(dest="repo_command")

    repo_subparsers.add_parser("status", help="저장소 상태 확인")
    repo_subparsers.add_parser("guide", help="GitHub 운영 가이드 생성")
    repo_subparsers.add_parser("snapshot", help="현재 프로젝트 구조 스냅샷 생성")


def handle_repo_command(kernel, args) -> None:
    if args.repo_command == "status":
        result = kernel.get_repository_status()
        print("\n=== Repository Status ===")
        print(f"project_path : {result['project_path']}")
        print(f"git_enabled  : {result['git_enabled']}")
        print(f"mode         : {result['mode']}")
        print(f"health       : {result['health']}")
        print("\nChecks")
        for check in result["checks"]:
            print(f"- [{check['status']}] {check['name']} : {check['message']}")
        return

    if args.repo_command == "guide":
        result = kernel.create_repository_guide()
        print("\n=== Repository Guide ===")
        print(f"status : {result['status']}")
        print(f"path   : {result['path']}")
        return

    if args.repo_command == "snapshot":
        result = kernel.create_repository_snapshot()
        print("\n=== Repository Snapshot ===")
        print(f"status : {result['status']}")
        print(f"path   : {result['path']}")
        print(f"files  : {result['file_count']}")
        print(f"dirs   : {result['dir_count']}")
        return

    print("repo 하위 명령어가 필요합니다.")
