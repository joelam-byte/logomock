"""Immutable local task versions and recoverable customer deliveries."""
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from app.models import Project, VersionManifest
from app.routers import project
from app.services.errors import AppError, FILE_NOT_FOUND, INVALID_PAYLOAD, WRITE_FAILED


VERSION_ID = re.compile(r'^version-\d{4}$')


def _version_number(version_id: str) -> int:
    if not VERSION_ID.fullmatch(version_id):
        raise AppError(INVALID_PAYLOAD, '版本编号无效')
    return int(version_id.rsplit('-', 1)[1])


def version_dir(name: str, version_id: str) -> Path:
    _version_number(version_id)
    return project.safe_file(name, f'versions/{version_id}')


def _version_paths(version_id: str) -> tuple[str, str]:
    return (
        f'versions/{version_id}/preview.png',
        f'versions/{version_id}/snapshot.json',
    )


def _read_manifest(name: str, version_id: str) -> VersionManifest:
    folder = version_dir(name, version_id)
    manifest_path = folder / 'manifest.json'
    if not manifest_path.is_file():
        raise AppError(FILE_NOT_FOUND, '版本存档不存在')
    try:
        manifest = VersionManifest.model_validate_json(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValidationError, ValueError) as exc:
        raise AppError(INVALID_PAYLOAD, '版本存档已损坏，无法读取') from exc

    expected_preview, expected_snapshot = _version_paths(version_id)
    if (
        manifest.version_id != version_id
        or manifest.number != _version_number(version_id)
        or manifest.preview_path != expected_preview
        or manifest.snapshot_path != expected_snapshot
        or not project.safe_file(name, manifest.preview_path).is_file()
        or not project.safe_file(name, manifest.snapshot_path).is_file()
    ):
        raise AppError(INVALID_PAYLOAD, '版本存档已损坏，无法读取')
    return manifest


def _cleanup_interrupted_staging(name: str) -> None:
    versions_dir = project.project_dir(name) / 'versions'
    if not versions_dir.is_dir():
        return
    for path in versions_dir.iterdir():
        if path.is_dir() and path.name.startswith('.pending-'):
            shutil.rmtree(path)


def list_versions(name: str) -> list[VersionManifest]:
    versions_dir = project.project_dir(name) / 'versions'
    results = []
    if versions_dir.is_dir():
        for folder in versions_dir.iterdir():
            if not folder.is_dir() or not VERSION_ID.fullmatch(folder.name):
                continue
            try:
                results.append(_read_manifest(name, folder.name))
            except AppError:
                continue
    return sorted(results, key=lambda item: item.number, reverse=True) + legacy_manifests(name)


def legacy_manifests(name: str) -> list[VersionManifest]:
    """Expose complete V1 export folders as restore-only version records."""
    output = project.project_dir(name) / 'output'
    if not output.is_dir():
        return []
    results = []
    for folder in sorted(output.glob('export-*'), reverse=True):
        if not folder.is_dir():
            continue
        snapshot_path = folder / 'snapshot.json'
        preview = next(iter(sorted(folder.glob('mockup-*.png'))), None)
        if not snapshot_path.is_file() or preview is None or not preview.is_file():
            continue
        try:
            snapshot = Project.model_validate_json(snapshot_path.read_text(encoding='utf-8'))
            scheme = snapshot.schemes[0] if len(snapshot.schemes) == 1 else None
            results.append(VersionManifest(
                version_id=f'legacy-{folder.name}',
                number=0,
                created_at=datetime.fromtimestamp(folder.stat().st_mtime, timezone.utc).isoformat(),
                source_revision=snapshot.revision,
                preview_path=preview.relative_to(project.project_dir(name)).as_posix(),
                snapshot_path=snapshot_path.relative_to(project.project_dir(name)).as_posix(),
                output_filename=preview.name,
                logo_width_mm=scheme.size_mm.w if scheme else 0,
                logo_height_mm=scheme.size_mm.h if scheme else 0,
                color=scheme.color if scheme and scheme.color in {'original', 'black', 'white', 'gray'} else 'original',
                read_only=True,
            ))
        except (OSError, ValidationError, ValueError):
            continue
    return results


def summary(name: str) -> tuple[int, str | None]:
    """Return complete stored-version count and newest preview path without writes."""
    versions = list_versions(name)
    return len(versions), versions[0].preview_path if versions else None


def _safe_output_filename(value: str) -> str:
    filename = Path(value).name if isinstance(value, str) else ''
    if filename != value or not filename or filename in {'.', '..'}:
        raise AppError(INVALID_PAYLOAD, '客户确认图文件名无效')
    return filename


def _write_delivery_temp(source: Path, destination: Path) -> Path:
    if not destination.parent.is_dir():
        raise AppError(WRITE_FAILED, '客户确认图保存位置不存在')
    temporary = destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.tmp')
    try:
        shutil.copyfile(source, temporary)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise AppError(WRITE_FAILED, f'客户确认图写入失败：{exc}') from exc
    return temporary


def _publish_delivery(temporary: Path, destination: Path) -> Path | None:
    backup = None
    try:
        if destination.exists():
            backup = destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.backup')
            os.replace(destination, backup)
        os.replace(temporary, destination)
        return backup
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        if backup is not None and backup.exists():
            os.replace(backup, destination)
        raise AppError(WRITE_FAILED, f'客户确认图写入失败：{exc}') from exc


def _rollback_delivery(destination: Path, backup: Path | None) -> None:
    destination.unlink(missing_ok=True)
    if backup is not None and backup.exists():
        os.replace(backup, destination)


def commit_version(
    name: str,
    source: Project,
    preview: Image.Image,
    output_filename: str,
    destination: Path,
) -> VersionManifest:
    """Publish one complete local version and one customer PNG, or roll back both."""
    output_filename = _safe_output_filename(output_filename)
    destination = Path(destination)
    staging = None
    delivery_temp = None
    delivery_backup = None
    with project.storage_lock():
        current = project.load(name)
        if current.revision != source.revision:
            raise AppError('REVISION_CONFLICT', '导出前任务已更新，请重新检查后再导出')
        _cleanup_interrupted_staging(name)
        number = current.next_version_number
        version_id = f'version-{number:04d}'
        versions_dir = project.project_dir(name) / 'versions'
        final = versions_dir / version_id
        if final.exists():
            raise AppError(INVALID_PAYLOAD, '版本目录已存在，无法覆盖')
        preview_path, snapshot_path = _version_paths(version_id)
        staging = versions_dir / f'.pending-{uuid.uuid4().hex}'
        staging.mkdir(parents=True)
        try:
            internal_preview = staging / 'preview.png'
            preview.convert('RGBA').save(internal_preview, format='PNG')
            with Image.open(internal_preview) as verified:
                verified.verify()
            manifest = VersionManifest(
                version_id=version_id,
                number=number,
                created_at=datetime.now(timezone.utc).isoformat(),
                source_revision=source.revision,
                preview_path=preview_path,
                snapshot_path=snapshot_path,
                output_filename=output_filename,
                logo_width_mm=source.schemes[0].size_mm.w if source.schemes else 0,
                logo_height_mm=source.schemes[0].size_mm.h if source.schemes else 0,
                color=(
                    source.schemes[0].color
                    if source.schemes and source.schemes[0].color in {'original', 'black', 'white', 'gray'}
                    else 'original'
                ),
            )
            project.atomic_write_json(staging / 'snapshot.json', source.model_dump())
            project.atomic_write_json(staging / 'manifest.json', manifest.model_dump())
            delivery_temp = _write_delivery_temp(internal_preview, destination)
            os.replace(staging, final)
            staging = None
            delivery_backup = _publish_delivery(delivery_temp, destination)
            delivery_temp = None
            updated = current.model_copy(deep=True)
            updated.next_version_number = number + 1
            try:
                project._commit(name, updated, current.revision)
            except Exception:
                _rollback_delivery(destination, delivery_backup)
                delivery_backup = None
                shutil.rmtree(final, ignore_errors=True)
                raise
            if delivery_backup is not None:
                delivery_backup.unlink(missing_ok=True)
            return manifest
        except AppError:
            raise
        except OSError as exc:
            raise AppError(WRITE_FAILED, f'版本存档写入失败：{exc}') from exc
        finally:
            if delivery_temp is not None:
                delivery_temp.unlink(missing_ok=True)
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)


def load_version(name: str, version_id: str) -> tuple[VersionManifest, Project]:
    if version_id.startswith('legacy-'):
        manifest = next((item for item in legacy_manifests(name) if item.version_id == version_id), None)
        if manifest is None:
            raise AppError(FILE_NOT_FOUND, '版本存档不存在')
    else:
        manifest = _read_manifest(name, version_id)
    try:
        snapshot = Project.model_validate_json(project.safe_file(name, manifest.snapshot_path).read_text(encoding='utf-8'))
    except (OSError, ValidationError, ValueError) as exc:
        raise AppError(INVALID_PAYLOAD, '版本存档已损坏，无法读取') from exc
    return manifest, snapshot


def restore_version(name: str, version_id: str, expected_revision: int) -> Project:
    with project.storage_lock():
        current = project.load(name)
        if current.revision != expected_revision:
            raise AppError('REVISION_CONFLICT', '任务已更新，请重新打开后再恢复版本')
        _, snapshot = load_version(name, version_id)
        restored = snapshot.model_copy(deep=True)
        restored.name = current.name
        restored.revision = current.revision
        restored.status = 'editing'
        restored.next_version_number = current.next_version_number
        return project._commit(name, restored, current.revision)


def delete_version(name: str, version_id: str) -> None:
    if version_id.startswith('legacy-'):
        raise AppError(INVALID_PAYLOAD, '旧版导出只读，不能删除')
    with project.storage_lock():
        folder = version_dir(name, version_id)
        if not folder.is_dir():
            raise AppError(FILE_NOT_FOUND, '版本存档不存在')
        shutil.rmtree(folder)
