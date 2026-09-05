from pathlib import Path
from xml.etree import ElementTree as ET
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from app.main import app
from app.engine.base import EngineError
from app.models import Asset, AssetObject, AssetPage, Candidate, Inputs, Rect
from app.routers import convert, project as repo
from app.services import pdf_pages
from app.services import assets, svg_document as svg
from app.services.svg_document import prepare_svg, select_svg
from app.services.assets import classify_objects, group_candidates
from app.services.raster_assets import clean_raster

NS = '{http://www.w3.org/2000/svg}'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    with TestClient(app) as value:
        yield value


def data(response):
    body = response.json()
    assert body['ok'], body
    return body['data']


def test_page_count_reads_all_pdf_pages(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    source = tmp_path / 'two-pages.pdf'
    with source.open('wb') as stream:
        writer.write(stream)

    assert pdf_pages.page_count(source) == 2


def test_grouped_wordmark_is_one_candidate_but_nested_background_is_separate(tmp_path):
    source = tmp_path / 'source.svg'
    source.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
      <g id="logo"><rect id="background" width="200" height="100" fill="white"/>
        <g id="word"><path id="s" d="M20 20h10v20H20z"/><path id="t" d="M35 20h10v20H35z"/></g>
      </g><text id="dimension" x="20" y="90">50 mm</text>
    </svg>''')
    root = svg.prefix_ids(svg.prepare_svg(source), 'page-0001--')
    objects = [
        AssetObject(id='page-0001--background', label='对象 1', box={'x': 0, 'y': 0, 'w': 200, 'h': 100}, reason='background', selected=False),
        AssetObject(id='page-0001--s', label='对象 2', box={'x': 20, 'y': 20, 'w': 10, 'h': 20}, selected=True),
        AssetObject(id='page-0001--t', label='对象 3', box={'x': 35, 'y': 20, 'w': 10, 'h': 20}, selected=True),
        AssetObject(id='page-0001--dimension', label='对象 4', box={'x': 20, 'y': 82, 'w': 40, 'h': 8}, reason='dimension', selected=False),
    ]

    page = assets.group_page_candidates(root, objects, page_id='page-0001', page_number=1)
    by_members = {frozenset(candidate.object_ids) for candidate in page.candidates}

    assert frozenset({'page-0001--s', 'page-0001--t'}) in by_members
    assert frozenset({'page-0001--background'}) in by_members
    assert frozenset({'page-0001--dimension'}) in by_members


def uploaded_two_page_pdf_project(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    source = io.BytesIO()
    writer.write(source)
    return data(client.post('/api/projects/sample/upload/logo', files={'file': ('source.pdf', source.getvalue(), 'application/pdf')}))


def test_analysis_keeps_failed_second_page_visible_and_does_not_silently_drop_it(monkeypatch, client):
    uploaded_two_page_pdf_project(client)

    class Engine:
        def available(self):
            return True

        def to_svg_page(self, _source, destination, number):
            destination.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect id="shape-{number}" width="20" height="10"/></svg>')

    def analyse_page(_path, _engine, _root, page_id, number):
        if number == 2:
            raise EngineError('CONVERT_FAILED', '页面内容损坏')
        return AssetPage(
            id=page_id, number=number, label=f'页面 {number}', source_svg='input/page.svg',
            source_preview='input/page.png', source_box={'x': 0, 'y': 0, 'w': 100, 'h': 50},
            candidates=[Candidate(id=f'{page_id}--candidate-1', label='组 1', object_ids=[f'{page_id}--mark'], box={'x': 10, 'y': 10, 'w': 40, 'h': 20})],
        )

    monkeypatch.setattr(convert, 'get_engine', lambda: Engine())
    monkeypatch.setattr(assets, 'analyse_svg_page', analyse_page)
    monkeypatch.setattr(
        convert,
        'apply_candidates',
        lambda asset, _ids, _root, _engine: (asset, 'input/clean.svg', 'input/clean.png'),
        raising=False,
    )

    result = data(client.post('/api/projects/sample/convert'))

    assert [page['number'] for page in result['asset']['pages']] == [1, 2]
    assert result['asset']['pages'][0]['error'] is None
    assert '第 2 页' in result['asset']['pages'][1]['error']


def ready_multi_candidate_project(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    item = repo.load('sample')
    first = Candidate(id='page-0001--candidate-1', label='组 1', object_ids=['page-0001--word'], box={'x': 10, 'y': 10, 'w': 40, 'h': 20})
    second = Candidate(id='page-0001--candidate-2', label='对象 1', object_ids=['page-0001--mark'], box={'x': 70, 'y': 10, 'w': 20, 'h': 20})
    page = AssetPage(id='page-0001', number=1, label='页面 1', source_svg='input/source.svg', source_preview='input/source.png', source_box={'x': 0, 'y': 0, 'w': 100, 'h': 60}, candidates=[first, second])
    item.asset = Asset(id='asset', kind='vector', pages=[page], selected_candidate_ids=[], selected_ids=[], width=40, height=20)
    item.inputs = Inputs(logo_source='input/source.pdf')
    repo.save('sample', item)
    return item.model_dump(), [first.id, second.id]


def test_select_candidates_unions_only_their_server_side_objects(client, monkeypatch):
    _project, candidate_ids = ready_multi_candidate_project(client)
    seen = {}

    def fake_apply(asset, chosen_ids, _project_root, _engine):
        seen['candidate_ids'] = chosen_ids
        asset.selected_candidate_ids = chosen_ids
        asset.selected_ids = ['page-0001--word', 'page-0001--mark']
        return asset, 'input/clean.svg', 'input/clean.png'

    monkeypatch.setattr(convert, 'apply_candidates', fake_apply)

    saved = data(client.post('/api/projects/sample/asset/select', json={'candidate_ids': candidate_ids}))

    assert saved['asset']['selected_candidate_ids'] == candidate_ids
    assert seen['candidate_ids'] == candidate_ids
    assert saved['asset']['selected_ids'] == ['page-0001--word', 'page-0001--mark']


def test_svg_selection_preserves_group_transforms_defs_and_nonzero_origin(tmp_path):
    source = tmp_path/'source.svg'
    source.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 100 60" fill="red"><defs><clipPath id="clip"><rect width="40" height="20"/></clipPath></defs><g transform="translate(20 30)"><rect id="logo" width="40" height="20" clip-path="url(#clip)"/><rect id="noise" x="70" width="10" height="10"/></g></svg>''')
    root = prepare_svg(source)
    result = select_svg(root,{'logo'},Rect(x=20,y=30,w=40,h=20))
    parsed = ET.fromstring(result)
    assert parsed.get('viewBox') == '20 30 40 20'
    assert parsed.find(NS+'svg').get('fill') == 'red'
    assert parsed.find(f'.//{NS}g').get('transform') == 'translate(20 30)'
    assert parsed.find(f'.//*[@id="noise"]').get('display') == 'none'
    assert parsed.find(f'.//*[@id="clip"]') is not None


def test_svg_rejects_active_and_external_content(tmp_path):
    for payload in ['<script/>','<image href="file:///C:/secret.png"/>','<style>@import "https://evil.test/x";</style>']:
        file = tmp_path/'bad.svg'
        file.write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{payload}</svg>')
        with pytest.raises(ValueError):
            prepare_svg(file)


def test_background_and_measurement_suggestions_do_not_remove_brand_text():
    items = [dict(id='bg',label='path',box=dict(x=0,y=0,w=200,h=100),tag='rect',text=''),
             dict(id='mark',label='path',box=dict(x=20,y=30,w=40,h=30),tag='path',text=''),
             dict(id='dim',label='text',box=dict(x=20,y=70,w=40,h=8),tag='text',text='50 mm'),
             dict(id='brand',label='text',box=dict(x=70,y=30,w=40,h=10),tag='text',text='GTTK')]
    objects = classify_objects(items,Rect(x=0,y=0,w=200,h=100))
    assert {o.id:o.reason for o in objects} == {'bg':'background','mark':None,'dim':'dimension','brand':None}
    assert next(o for o in objects if o.id=='brand').selected


def test_separated_artwork_produces_candidates_while_nearby_parts_stay_together():
    items=[dict(id='a',label='a',box=dict(x=0,y=0,w=20,h=20),tag='path',text=''),
           dict(id='b',label='b',box=dict(x=21,y=0,w=5,h=20),tag='path',text=''),
           dict(id='c',label='c',box=dict(x=100,y=0,w=25,h=20),tag='path',text='')]
    objects=classify_objects(items,Rect(x=0,y=0,w=200,h=100))
    groups=group_candidates(objects)
    assert {frozenset(g.object_ids) for g in groups} == {frozenset({'a','b'}),frozenset({'c'})}


def test_raster_removes_edge_background_but_keeps_white_inside_logo():
    image=Image.new('RGBA',(100,60),'white')
    draw=ImageDraw.Draw(image)
    draw.rectangle((20,10,60,50),fill='black')
    draw.rectangle((30,20,50,40),fill='white')
    cleaned, components=clean_raster(image)
    assert cleaned.getpixel((0,0))[3] == 0
    assert cleaned.getpixel((40,30)) == (255,255,255,255)
    assert cleaned.getbbox() == (20,10,61,51)
    assert len(components) == 1


@pytest.mark.parametrize('body,selection,box,size',[
    ('<rect id="original" width="20" height="20" fill="blue"/><use id="clone" href="#original" x="50" y="50"/>','clone',Rect(x=50,y=50,w=20,h=20),(20,20)),
    ('<rect id="percent" x="25%" y="25%" width="50%" height="50%" fill="blue"/>','percent',Rect(x=25,y=25,w=50,h=50),(50,50)),
    ('<g id="group"><rect width="20" height="20" fill="blue"/><rect x="20" width="20" height="20" fill="blue"/></g><use id="clone" href="#group" x="50" y="50"/>','clone',Rect(x=50,y=50,w=40,h=20),(40,20)),
])
def test_selected_svg_renders_full_art_for_references_and_percentages(tmp_path,body,selection,box,size):
    from app.config import get_engine
    engine=get_engine()
    if not engine.available():
        pytest.skip('Real Inkscape selection fidelity test')
    source=tmp_path/'source.svg'
    source.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">{body}</svg>')
    selected=tmp_path/'selected.svg'
    selected.write_text(select_svg(prepare_svg(source),{selection},box))
    engine.svg_to_png(selected,tmp_path/'selected.png')
    with Image.open(tmp_path/'selected.png') as image:
        assert image.size==size
        assert image.getbbox()==(0,0,*size)
        assert image.getpixel((size[0]-2,size[1]-2))==(0,0,255,255)
