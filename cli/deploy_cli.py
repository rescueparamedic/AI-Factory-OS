from __future__ import annotations

def register_deploy_commands(subparsers):
    deploy_parser = subparsers.add_parser("deploy", help="Deployment Engine")
    deploy_subparsers = deploy_parser.add_subparsers(dest="deploy_command")

    create_parser = deploy_subparsers.add_parser("create", help="Release 기반 배포 후보 생성")
    create_parser.add_argument("--release", default=None)
    create_parser.add_argument("--env", default="staging", choices=["dev", "staging", "production"])
    create_parser.add_argument("--apply", action="store_true")

    deploy_subparsers.add_parser("latest", help="최신 Deployment 결과 보기")

    list_parser = deploy_subparsers.add_parser("list", help="Deployment 목록")
    list_parser.add_argument("--limit", type=int, default=10)

    rollback_parser = deploy_subparsers.add_parser("rollback", help="Rollback Point 확인")
    rollback_parser.add_argument("--deploy", default=None)

def _print_deploy(result):
    print("\n=== Deployment Engine Result ===")
    for key in ["status","deploy_id","release_id","environment","mode","version","package_path","manifest_path","rollback_path","deploy_path","report_path","next_stage"]:
        print(f"{key:14}: {result.get(key, '')}")
    if result.get("warnings"):
        print("\nWarnings")
        for item in result["warnings"]:
            print(f"- {item}")

def _no_release():
    print("\n=== Deployment 안내 ===")
    print("No Release Package Found.")
    print("Deployment를 생성하려면 먼저 Release가 필요합니다.")
    print("\nSuggested commands")
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" approve approve')
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" release create')
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" release latest')

def _no_deployment():
    print("\n=== Deployment 안내 ===")
    print("No Deployment Found.")
    print("아직 생성된 Deployment가 없습니다.")
    print("\nSuggested command")
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" deploy create')

def _no_rollback():
    print("\n=== Rollback 안내 ===")
    print("Nothing to rollback.")
    print("Deployment history is empty.")
    print("\nSuggested command")
    print('python "C:\\AIFactory\\AI Factory OS\\main.py" deploy create')

def handle_deploy_command(kernel, args):
    try:
        if args.deploy_command == "create":
            _print_deploy(kernel.create_deployment(release_id=args.release, environment=args.env, apply=args.apply))
            return
        if args.deploy_command == "latest":
            _print_deploy(kernel.get_latest_deployment())
            return
        if args.deploy_command == "list":
            items = kernel.list_deployments(limit=args.limit)
            print("\n=== Deployment 목록 ===")
            if not items:
                _no_deployment()
                return
            for item in items:
                print(f"{item.get('deploy_id')} | {item.get('environment')} | {item.get('status')} | {item.get('created_at')}")
            return
        if args.deploy_command == "rollback":
            result = kernel.get_deployment_rollback(deploy_id=args.deploy)
            print("\n=== Deployment Rollback Point ===")
            print(f"deploy_id     : {result.get('deploy_id', '')}")
            print(f"status        : {result.get('status', '')}")
            print(f"rollback_path : {result.get('rollback_path', '')}")
            print(f"message       : {result.get('message', '')}")
            return
        print("deploy 하위 명령어가 필요합니다.")
    except FileNotFoundError as exc:
        msg = str(exc).lower()
        if "release" in msg:
            _no_release()
        elif "deployment" in msg and args.deploy_command == "rollback":
            _no_rollback()
        elif "deployment" in msg:
            _no_deployment()
        else:
            print("\n=== Deployment 오류 ===")
            print(str(exc))
    except PermissionError as exc:
        print("\n=== Deployment 권한 오류 ===")
        print(str(exc))
