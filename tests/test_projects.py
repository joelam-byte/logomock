import io
import json
import math

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models import Project
from app.routers import project as repo
from app.services.errors import AppError


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    with TestClient(app) as c:
        yield c


def data(response):
    body = response.json()
    assert body['ok'], body
    return body['data']


def calibrated():
    return dict(name='sample', calibration=dict(product_frame=dict(x=0,y=0,w=400,h=200), width_mm=200),
                frames=[dict(id='f1',name='front',x=20,y=30,w=300,h=150)],
                schemes=[dict(id='A',frame_id='f1',size_mm=dict(w=50,h=20),offset_mm=dict(left=10,bottom=15))])


def test_recalibration_preserves_physical_size_and_projects_pixels(client):
    p = data(client.post('/api/projects',json={'name':'sample'}))
    p.update(calibrated())
    p = data(client.put('/api/projects/sample',json=p))
    assert p['schemes'][0]['logo_px'] == dict(x=40,y=110,w=100,h=40)
    p['calibration']['width_mm'] = 400
    p = data(client.put('/api/projects/sample',json=p))
    assert p['schemes'][0]['logo_px'] == dict(x=30,y=145,w=50,h=20)
    assert p['schemes'][0]['size_mm'] == dict(w=50,h=20)


def test_stale_save_cannot_overwrite_newer_order(client):
    p = data(client.post('/api/projects',json={'name':'sample'}))
    fresh = data(client.put('/api/projects/sample',json=p))
    old = client.put('/api/projects/sample',json=p).json()
    assert old['ok'] is False
    assert old['error']['code'] == 'REVISION_CONFLICT'
    assert data(client.get('/api/projects/sample'))['revision'] == fresh['revision']


@pytest.mark.parametrize('name',['..','.','CON','a/b','x\\y','a.',' '])
def test_project_name_cannot_escape_or_alias_windows_paths(client,name):
    assert client.post('/api/projects',json={'name':name}).json()['ok'] is False


def test_reject_nonfinite_and_negative_geometry():
    for value in [math.inf, math.nan, -1]:
        with pytest.raises(ValueError):
            Project.model_validate({'calibration':{'width_mm':value}})


def test_legacy_open_does_not_rewrite_order(client):
    path = repo.PROJECTS_DIR / 'legacy' / 'project.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({'name':'legacy','schemes':[]})
    path.write_text(original)
    assert data(client.get('/api/projects/legacy'))['revision'] == 0
    assert path.read_text() == original


def test_legacy_project_reads_with_v3_defaults_without_rewrite(client):
    path = repo.PROJECTS_DIR / 'legacy' / 'project.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({'name': 'legacy', 'schemes': []})
    path.write_text(original, encoding='utf-8')

    loaded = data(client.get('/api/projects/legacy'))

    assert loaded['status'] == 'editing'
    assert loaded['next_version_number'] == 1
    assert path.read_text(encoding='utf-8') == original


def test_legacy_named_logo_color_remains_readable():
    project = Project.model_validate({'schemes': [{'id': 'legacy', 'color': 'PANTONE 186 C'}]})

    assert project.schemes[0].color == 'PANTONE 186 C'


def test_v2_asset_is_exposed_as_one_page_without_rewriting_disk(client):
    path = repo.PROJECTS_DIR / 'legacy' / 'project.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({
        'name': 'legacy',
        'asset': {
            'id': 'a', 'kind': 'vector', 'source_svg': 'input/source.svg',
            'source_preview': 'input/source.png', 'width': 40, 'height': 20,
            'source_box': {'x': 0, 'y': 0, 'w': 40, 'h': 20},
            'objects': [], 'candidates': [], 'selected_ids': [], 'warnings': [],
        },
    })
    path.write_text(original, encoding='utf-8')

    loaded = data(client.get('/api/projects/legacy'))

    assert loaded['asset']['pages'][0]['number'] == 1
    assert path.read_text(encoding='utf-8') == original


def test_project_list_exposes_version_summary_without_reading_output_files(client):
    data(client.post('/api/projects', json={'name': 'sample'}))

    listed = data(client.get('/api/projects'))[0]

    assert listed == {
        'name': 'sample',
        'revision': 1,
        'updated_at': listed['updated_at'],
        'has_bag': False,
        'has_logo': False,
        'status': 'editing',
        'version_count': 0,
        'preview_path': None,
    }


def test_replacing_logo_invalidates_derived_asset_and_keeps_original(client):
    p = data(client.post('/api/projects',json={'name':'sample'}))
    p['inputs'] = dict(logo_source='input/old.svg',logo_svg='input/old-clean.svg',logo_preview='input/old.png')
    repo.save('sample',Project.model_validate(p))
    original = repo.input_dir('sample') / 'old.svg'
    original.write_text('<svg/>')
    p = data(client.post('/api/projects/sample/upload/logo',files={'file':('logo.svg',b'<svg xmlns="http://www.w3.org/2000/svg"/>','image/svg+xml')}))
    assert p['inputs']['logo_svg'] is None
    assert p['inputs']['logo_preview'] is None
    assert p['asset'] is None
    assert p['inputs']['logo_source'] != 'input/old.svg'
    assert original.read_text() == '<svg/>'


def test_clone_is_independent_and_listing_opens_saved_orders(client):
    data(client.post('/api/projects',json={'name':'sample'}))
    copy = data(client.post('/api/projects/sample/clone',json={'name':'copy'}))
    assert copy['name'] == 'copy'
    assert {p['name'] for p in data(client.get('/api/projects'))} == {'sample','copy'}


def test_delete_project_removes_only_the_selected_task_and_its_files(client):
    data(client.post('/api/projects', json={'name': 'mistake-copy'}))
    data(client.post('/api/projects', json={'name': 'keep'}))
    (repo.input_dir('mistake-copy') / 'logo.ai').write_text('temporary copy', encoding='utf-8')

    result = data(client.delete('/api/projects/mistake-copy'))

    assert result == {'deleted': 'mistake-copy'}
    assert not repo.project_dir('mistake-copy').exists()
    assert (repo.project_dir('keep') / 'project.json').is_file()
    assert [item['name'] for item in data(client.get('/api/projects'))] == ['keep']


def test_file_path_prefix_does_not_allow_sibling_directory(client):
    data(client.post('/api/projects',json={'name':'sample'}))
    sibling=repo.PROJECTS_DIR / 'sample-secret'
    sibling.mkdir()
    (sibling/'secret.txt').write_text('private')
    with pytest.raises(AppError):
        repo.get_file('sample','../sample-secret/secret.txt')


def test_export_snapshot_is_immutable_and_stale_revision_is_rejected(client):
    data(client.post('/api/projects',json={'name':'sample'}))
    bag=io.BytesIO()
    Image.new('RGB',(400,300),'white').save(bag,format='PNG')
    data(client.post('/api/projects/sample/upload/bag',files={'file':('bag.png',bag.getvalue(),'image/png')}))
    logo=io.BytesIO()
    Image.new('RGBA',(40,20),'blue').save(logo,format='PNG')
    data(client.post('/api/projects/sample/upload/logo',files={'file':('logo.png',logo.getvalue(),'image/png')}))
    p=data(client.post('/api/projects/sample/convert'))
    p.update(calibrated())
    p=data(client.put('/api/projects/sample',json=p))
    payload=dict(scheme_ids=['A'],formats=['png','svg'],revision=p['revision'])
    result=data(client.post('/api/projects/sample/export',json=payload))
    assert result['revision']==p['revision']
    png=next(file for file in result['files'] if file.endswith('.png'))
    original=repo.safe_file('sample',png).read_bytes()
    p['schemes'][0]['size_mm']['w']=80
    p=data(client.put('/api/projects/sample',json=p))
    stale=client.post('/api/projects/sample/export',json=payload).json()
    assert not stale['ok']
    assert stale['error']['code']=='REVISION_CONFLICT'
    payload['revision']=p['revision']
    newer=data(client.post('/api/projects/sample/export',json=payload))
    assert set(newer['files']).isdisjoint(result['files'])
    assert repo.safe_file('sample',png).read_bytes()==original


def test_windows_mjs_response_is_executable_javascript(client):
    response=client.get('/web/workspace/main.mjs')
    assert response.status_code==200
    assert response.headers['content-type'].split(';')[0] in {'text/javascript','application/javascript'}
