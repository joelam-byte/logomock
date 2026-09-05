import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models import Project
from app.routers import project as repo
from app.services import version_store as versions
from app.services.errors import AppError


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    with TestClient(app) as value:
        yield value


def data(response):
    body = response.json()
    assert body['ok'], body
    return body['data']


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


def test_version_routes_restore_only_from_current_revision(client, tmp_path):
    source = data(client.post('/api/projects', json={'name': 'sample'}))
    delivered = tmp_path / 'sent.png'
    versions.commit_version(
        'sample', Project.model_validate(source), Image.new('RGBA', (20, 20), 'white'), 'sent.png', delivered
    )

    listed = data(client.get('/api/projects/sample/versions'))
    assert listed[0]['version_id'] == 'version-0001'

    stale = client.post('/api/projects/sample/versions/version-0001/restore', json={'revision': 0}).json()
    assert stale['ok'] is False
    assert stale['error']['code'] == 'REVISION_CONFLICT'

    current = data(client.get('/api/projects/sample'))
    restored = data(client.post('/api/projects/sample/versions/version-0001/restore', json={'revision': current['revision']}))
    assert restored['revision'] == current['revision'] + 1

    assert data(client.delete('/api/projects/sample/versions/version-0001')) == {'deleted': 'version-0001'}


def test_legacy_output_snapshot_is_listed_read_only_and_can_restore(client):
    project = data(client.post('/api/projects', json={'name': 'sample'}))
    legacy = repo.project_dir('sample') / 'output' / 'export-legacy'
    legacy.mkdir(parents=True)
    repo.atomic_write_json(legacy / 'snapshot.json', project)
    Image.new('RGBA', (20, 20), 'white').save(legacy / 'mockup-01-A.png')

    item = data(client.get('/api/projects/sample/versions'))[0]

    assert item['version_id'] == 'legacy-export-legacy'
    assert item['read_only'] is True
    assert data(client.post(f"/api/projects/sample/versions/{item['version_id']}/restore", json={'revision': project['revision']}))
    deleted = client.delete(f"/api/projects/sample/versions/{item['version_id']}").json()
    assert deleted['ok'] is False
