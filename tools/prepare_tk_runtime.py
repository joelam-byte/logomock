"""Materialize an ignored Tcl/Tk runtime before a Windows portable build."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


RUNTIME_DIR = Path(__file__).parent / 'tk-runtime'


def find_runtime(roots: list[Path]) -> Path | None:
    """Return the directory directly containing a matching tcl/tk pair."""
    for root in roots:
        for candidate in (root / 'tcl', root / 'Library' / 'lib', root):
            if (candidate / 'tcl8.6').is_dir() and (candidate / 'tk8.6').is_dir():
                return candidate
    return None


def candidate_roots() -> list[Path]:
    base = Path(sys.base_prefix)
    package_libs = sorted((base / 'pkgs').glob('tk-*/Library/lib'))
    return [base, *package_libs]


def main() -> None:
    if (RUNTIME_DIR / 'tcl8.6').is_dir() and (RUNTIME_DIR / 'tk8.6').is_dir():
        print(f'Tcl/Tk runtime is ready: {RUNTIME_DIR}')
        return
    source = find_runtime(candidate_roots())
    if source is None:
        raise SystemExit('无法找到 Tcl/Tk 运行时。请使用含 Tk 的 Windows Python 或 Conda Python 构建。')
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    for name in ('tcl8.6', 'tk8.6'):
        shutil.copytree(source / name, RUNTIME_DIR / name, dirs_exist_ok=True)
    print(f'Prepared Tcl/Tk runtime from: {source}')


if __name__ == '__main__':
    main()
