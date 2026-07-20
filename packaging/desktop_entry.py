'''PyInstaller entry point for AI Factory Desktop.'''


def main() -> int:
    from afde.desktop.app import main as desktop_main

    return desktop_main()


if __name__ == '__main__':
    raise SystemExit(main())
