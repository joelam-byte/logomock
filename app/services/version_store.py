"""Read-only version summaries used by the task list.

Full version creation and restore operations live here in the next implementation step.
"""
import json
import re

from app.routers import project


VERSION_ID = re.compile(r'^version-\d{4}$')


def summary(name: str) -> tuple[int, str | None]:
    """Return complete stored-version count and newest preview path without writes."""
    versions_dir = project.project_dir(name) / 'versions'
    if not versions_dir.is_dir():
        return 0, None

    versions = []
    for folder in versions_dir.iterdir():
        if not folder.is_dir() or not VERSION_ID.fullmatch(folder.name):
            continue
        manifest_path = folder / 'manifest.json'
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            preview = manifest.get('preview_path')
            if isinstance(preview, str) and project.safe_file(name, preview).is_file():
                versions.append((folder.name, preview))
        except (OSError, ValueError, TypeError):
            continue

    if not versions:
        return 0, None
    return len(versions), max(versions)[1]
