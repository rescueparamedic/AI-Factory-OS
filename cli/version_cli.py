from __future__ import annotations


def register_version_commands(subparsers):
    subparsers.add_parser("version", help="현재 OS 버전 확인")


def handle_version_command(kernel, args) -> None:
    version = kernel.get_version()
    print("\n=== AI Factory OS Version ===")
    print(f"version : {version['version']}")
    print(f"sprint  : {version['sprint']}")
    print(f"build   : {version['build']}")
    print(f"status  : {version['status']}")
