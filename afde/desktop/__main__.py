"""Run AI Factory Desktop with ``python -m afde.desktop``."""


def _main() -> int:
    try:
        from .app import main
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            print("Status: Failed")
            print("Error: PySide6 is not installed.")
            print("Cause: AI Factory Desktop requires the optional GUI dependency.")
            print("Next: python -m pip install -r requirements-desktop.txt")
            return 2
        raise
    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
