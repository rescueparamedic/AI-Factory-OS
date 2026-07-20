'''Path helpers for source and frozen Desktop execution.'''
from pathlib import Path
import sys

APPLICATION_NAME = 'AI Factory Desktop'
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_frozen(runtime=sys) -> bool:
    return bool(getattr(runtime, 'frozen', False))


def resource_root(runtime=sys) -> Path:
    '''Resolve bundled resources without relocating user data.'''
    if not is_frozen(runtime):
        return PROJECT_ROOT
    bundled = getattr(runtime, '_MEIPASS', None)
    if bundled:
        return Path(bundled).resolve()
    return Path(runtime.executable).resolve().parent


def expected_executable_path(project_root=None) -> Path:
    root = Path(project_root).resolve() if project_root else PROJECT_ROOT
    return root / 'dist' / APPLICATION_NAME / f'{APPLICATION_NAME}.exe'
