import json

import pytest
from PIL import Image

from app.routers import project as repo
from app.services import version_store as versions
from app.services.errors import AppError


def test_committed_version_restores_draft_and_keeps_customer_png(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    source = repo.create('sample')
    delivered = tmp_path / 'customer.png'

    manifest = versions.commit_version(
        'sample', source, Image.new('RGBA', (40, 30), 'white'), 'customer.png', delivered
    )

    assert manifest.version_id == 'version-0001'
    assert delivered.is_file()
    assert versions.list_versions('sample') == [manifest]
    assert repo.safe_file('sample', manifest.preview_path).is_file()

    changed = repo.load('sample')
    changed.status = 'completed'
    changed = repo.save('sample', changed)
    restored = versions.restore_version('sample', manifest.version_id, changed.revision)

    assert restored.status == 'editing'
    assert restored.next_version_number == 2
    assert versions.load_version('sample', manifest.version_id)[0] == manifest

    versions.delete_version('sample', manifest.version_id)

    assert versions.list_versions('sample') == []
    assert delivered.is_file()


def test_failed_external_delivery_leaves_no_version_or_number_advance(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    source = repo.create('sample')
    missing_parent = tmp_path / 'not-created' / 'customer.png'

    with pytest.raises(AppError) as error:
        versions.commit_version(
            'sample', source, Image.new('RGBA', (40, 30), 'white'), 'customer.png', missing_parent
        )

    assert error.value.code == 'WRITE_FAILED'
    assert versions.list_versions('sample') == []
    assert repo.load('sample').next_version_number == 1


def test_version_store_ignores_incomplete_staging_and_rejects_tampered_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    repo.create('sample')
    versions_dir = repo.project_dir('sample') / 'versions'
    (versions_dir / '.pending-interrupted').mkdir(parents=True)
    broken = versions_dir / 'version-0001'
    broken.mkdir()
    (broken / 'manifest.json').write_text(json.dumps({'version_id': 'version-9999'}), encoding='utf-8')

    assert versions.list_versions('sample') == []
    with pytest.raises(AppError) as error:
        versions.load_version('sample', 'version-0001')
    assert error.value.code == 'INVALID_PAYLOAD'
    with pytest.raises(AppError):
        versions.delete_version('sample', '../project.json')
