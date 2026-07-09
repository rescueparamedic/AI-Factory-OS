from __future__ import annotations

def register_release_commands(subparsers):
    release_parser = subparsers.add_parser("release", help="Release Management")
    release_subparsers = release_parser.add_subparsers(dest="release_command")

    create_parser = release_subparsers.add_parser("create", help="승인된 항목으로 Release 생성")
    create_parser.add_argument("--approval", default=None)
    create_parser.add_argument("--type", default="patch", choices=["patch", "minor", "major"])

    release_subparsers.add_parser("latest", help="최신 Release 결과 보기")

    list_parser = release_subparsers.add_parser("list", help="Release 목록")
    list_parser.add_argument("--limit", type=int, default=10)

def _print_release(result):
    print("\n=== Release Management Result ===")
    for key in ["status","release_id","approval_id","product_id","version","release_type","package_path","manifest_path","sha256","release_path","release_notes_path","next_stage"]:
        print(f"{key:15}: {result.get(key, '')}")
    print("\nArtifacts")
    for item in result.get("artifacts", []):
        print(f"- {item.get('type')} | {item.get('path')}")

def _no_approval():
    print("\n=== Release 안내 ===")
    print("No approved Approval item found.")
    print("Release를 생성하려면 먼저 승인된 Approval이 필요합니다.")
    print("\nSuggested commands")
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" pipeline run --request "작업 요청"')
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" approve latest')
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" approve approve')
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" release create')

def _no_release():
    print("\n=== Release 안내 ===")
    print("No Release Found.")
    print("아직 생성된 Release가 없습니다.")
    print("\nSuggested command")
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" release create')

def handle_release_command(kernel, args):
    try:
        if args.release_command == "create":
            _print_release(kernel.create_release(approval_id=args.approval, release_type=args.type))
            return
        if args.release_command == "latest":
            _print_release(kernel.get_latest_release())
            return
        if args.release_command == "list":
            items = kernel.list_releases(limit=args.limit)
            print("\n=== Release 목록 ===")
            if not items:
                _no_release()
                return
            for item in items:
                print(f"{item.get('release_id')} | {item.get('version')} | {item.get('status')} | {item.get('created_at')}")
            return
        print("release 하위 명령어가 필요합니다.")
    except FileNotFoundError as exc:
        msg = str(exc).lower()
        if "approved" in msg or "approval" in msg:
            _no_approval()
        elif "release" in msg:
            _no_release()
        else:
            print("\n=== Release 오류 ===")
            print(str(exc))
    except PermissionError as exc:
        print("\n=== Release 권한 오류 ===")
        print(str(exc))
