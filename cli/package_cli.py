from __future__ import annotations


def register_package_commands(subparsers):
    package_parser = subparsers.add_parser("package", help="Patch Package 검사/관리")
    package_subparsers = package_parser.add_subparsers(dest="package_command")

    validate_parser = package_subparsers.add_parser("validate", help="패치 ZIP 안전성 검사")
    validate_parser.add_argument("--path", required=True, help="검사할 ZIP 경로")


def handle_package_command(kernel, args) -> None:
    if args.package_command == "validate":
        result = kernel.validate_patch_package(args.path)
        print("\n=== Package Validate ===")
        print(f"status      : {result['status']}")
        print(f"safe        : {result['safe']}")
        print(f"file_count  : {result['file_count']}")
        print(f"sha256      : {result['sha256']}")
        print(f"report_path : {result.get('report_path', '')}")

        if result.get("blocked"):
            print("\nBlocked")
            for item in result["blocked"]:
                print(f"- {item}")
        return

    print("package 하위 명령어가 필요합니다.")
