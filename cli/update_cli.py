from __future__ import annotations


def register_update_commands(subparsers):
    update_parser = subparsers.add_parser("update", help="Update Manager")
    update_subparsers = update_parser.add_subparsers(dest="update_command")
    update_subparsers.add_parser("backup", help="현재 프로젝트 백업 생성")
    update_subparsers.add_parser("check", help="업데이트 가능 상태 점검")
    update_subparsers.add_parser("history", help="업데이트 이력 보기")
    update_subparsers.add_parser("rollback", help="최근 백업으로 롤백")
    update_subparsers.add_parser("find", help="updates 폴더의 최신 패치 찾기")
    update_subparsers.add_parser("preview", help="설치 예정 패치 미리보기")

    install_parser = update_subparsers.add_parser("install", help="패치 ZIP 자동 설치")
    install_parser.add_argument("patch_path", nargs="?", default=None, help="설치할 패치 ZIP 경로. 생략 시 updates 폴더에서 자동 검색")
    install_parser.add_argument("--yes", action="store_true", help="확인 질문 없이 설치")


def print_patch_preview(preview: dict) -> None:
    print("\n=== Patch Preview ===")
    print(f"found           : {preview['found']}")
    print(f"message         : {preview['message']}")
    if not preview["found"]:
        return
    print(f"current_version : {preview.get('current_version', '')}")
    print(f"new_version     : {preview.get('patch_version', '')}")
    print(f"sprint          : {preview.get('sprint', '')}")
    print(f"patch_path      : {preview.get('patch_path', '')}")
    print(f"files           : {preview.get('file_count', 0)}")
    print(f"description     : {preview.get('description', '')}")
    print("\nFiles")
    for item in preview.get("files", []):
        print(f"- {item}")


def handle_update_command(kernel, args) -> None:
    if args.update_command == "backup":
        result = kernel.create_backup()
        print("\n=== Update Manager Backup ===")
        print(f"status      : {result['status']}")
        print(f"backup_path : {result['backup_path']}")
        print(f"files       : {result['files_copied']}")
        return

    if args.update_command == "check":
        result = kernel.check_update_readiness()
        print("\n=== Update Readiness Check ===")
        print(f"ready  : {result['ready']}")
        print(f"status : {result['status']}")
        print(f"updates_dir : {result.get('updates_dir', '')}")
        for item in result["checks"]:
            print(f"- [{item['status']}] {item['name']} : {item['message']}")
        return

    if args.update_command == "find":
        result = kernel.find_latest_patch()
        print("\n=== Latest Patch Finder ===")
        print(f"found      : {result['found']}")
        print(f"message    : {result['message']}")
        print(f"patch_path : {result.get('patch_path', '')}")
        return

    if args.update_command == "preview":
        print_patch_preview(kernel.preview_patch())
        return

    if args.update_command == "install":
        preview = kernel.preview_patch(args.patch_path)
        print_patch_preview(preview)
        if not preview["found"]:
            return

        proceed = args.yes
        if not proceed:
            answer = input("\n설치하시겠습니까? (Y/N): ").strip().lower()
            proceed = answer in {"y", "yes"}

        if not proceed:
            print("\n설치를 취소했습니다.")
            return

        result = kernel.install_patch(args.patch_path)
        print("\n=== Update Install ===")
        print(f"status       : {result['status']}")
        print(f"message      : {result['message']}")
        print(f"patch        : {result.get('patch_path', '')}")
        print(f"backup_path  : {result.get('backup_path', '')}")
        print(f"files_copied : {result.get('files_copied', 0)}")
        print(f"history_path : {result.get('history_path', '')}")
        return

    if args.update_command == "rollback":
        result = kernel.rollback_update()
        print("\n=== Update Rollback ===")
        print(f"status      : {result['status']}")
        print(f"message     : {result['message']}")
        print(f"backup_path : {result.get('backup_path', '')}")
        print(f"files_restored : {result.get('files_restored', 0)}")
        return

    if args.update_command == "history":
        result = kernel.get_update_history()
        print("\n=== Update History ===")
        if not result["items"]:
            print("업데이트 이력이 없습니다.")
            return
        for item in result["items"]:
            print(f"{item.get('timestamp')} | {item.get('status')} | {item.get('patch_version')} | {item.get('message')}")
        return

    print("update 하위 명령어가 필요합니다.")
