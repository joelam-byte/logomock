import base64
import io
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_engine
from app.main import app
from app.models import Rect, Scheme,Frame
from app.routers import export as export_router
from app.routers import project as repo
from app.services import customer_export, placement_png, placement_svg, save_dialog, selection_png, spec_svg, svg_document

NS='{http://www.w3.org/2000/svg}'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, 'PROJECTS_DIR', tmp_path / 'projects')
    with TestClient(app) as value:
        yield value


def data(response):
    body = response.json()
    assert body['ok'], body
    return body['data']


def ready_project(client):
    data(client.post('/api/projects', json={'name': 'sample'}))
    bag = io.BytesIO()
    Image.new('RGB', (400, 300), 'white').save(bag, format='PNG')
    data(client.post('/api/projects/sample/upload/bag', files={'file': ('bag.png', bag.getvalue(), 'image/png')}))
    logo_file = io.BytesIO()
    Image.new('RGBA', (40, 20), 'blue').save(logo_file, format='PNG')
    project = data(client.post('/api/projects/sample/upload/logo', files={'file': ('logo.png', logo_file.getvalue(), 'image/png')}))
    project = data(client.post('/api/projects/sample/convert'))
    project.update({
        'calibration': {'product_frame': {'x': 0, 'y': 0, 'w': 400, 'h': 300}, 'width_mm': 200},
        'frames': [{'id': 'front', 'name': 'front', 'x': 0, 'y': 0, 'w': 400, 'h': 300}],
        'schemes': [{'id': 'active', 'frame_id': 'front', 'size_mm': {'w': 50, 'h': 25}, 'offset_mm': {'left': 20, 'bottom': 20}}],
    })
    return data(client.put('/api/projects/sample', json=project))


def logo(tmp_path):
    path=tmp_path/'logo.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" fill="red" width="40" height="20" viewBox="10 30 40 20"><rect id="art" x="10" y="30" width="40" height="20"/></svg>')
    return path


def test_artwork_svg_is_exact_physical_size_and_preserves_source_viewbox(tmp_path):
    scheme=Scheme(size_mm={'w':50,'h':25})
    root=ET.fromstring(spec_svg.build_artwork(logo(tmp_path),scheme))
    assert root.get('width')=='50mm'
    assert root.get('height')=='25mm'
    nested=root.find(NS+'svg')
    assert nested.get('viewBox')=='10 30 40 20'
    assert nested.get('width')=='50'
    assert nested.get('height')=='25'
    assert nested.get('fill')=='red'


def test_clean_png_has_no_frames_badges_or_labels(tmp_path):
    bag=tmp_path/'bag.png'
    art=tmp_path/'art.png'
    Image.new('RGB',(100,80),(220,210,200)).save(bag)
    Image.new('RGBA',(20,10),(0,0,255,255)).save(art)
    scheme=Scheme(logo_px={'x':30,'y':25,'w':40,'h':20},size_mm={'w':50,'h':25})
    result=selection_png.render(bag,art,scheme)
    assert result.size==(100,80)
    assert result.getpixel((0,0))[:3]==(220,210,200)
    assert result.getpixel((50,35))[:3]==(0,0,255)
    assert set(result.convert('RGB').get_flattened_data())=={(220,210,200),(0,0,255)}


def test_placement_embeds_photo_and_artwork_and_uses_readable_mm_text(tmp_path):
    bag=tmp_path/'bag.png'
    Image.new('RGB',(800,800),'white').save(bag)
    scheme=Scheme(id='A',logo_px={'x':200,'y':300,'w':100,'h':50},size_mm={'w':50,'h':25},offset_mm={'left':10,'bottom':15})
    root=ET.fromstring(placement_svg.build(bag,800,800,Frame(x=180,y=200,w=400,h=300),scheme,logo_path=logo(tmp_path)))
    image=root.find('.//'+NS+'image')
    assert image.get('href').startswith('data:image/png;base64,')
    assert base64.b64decode(image.get('href').split(',',1)[1]).startswith(bytes([137,80,78,71]))
    assert root.find('.//*[@id="art"]') is not None
    assert any(float(n.get('font-size','0'))>=3 for n in root.iter(NS+'text'))


def test_large_logo_downsampling_averages_fine_detail_without_aliasing(tmp_path):
    bag=tmp_path/'bag.png'
    art=tmp_path/'stripes.png'
    Image.new('RGB',(32,32),'white').save(bag)
    logo=Image.new('RGB',(256,256))
    logo.putdata([(255,255,255) if ((x+3)//8)%2 else (0,0,0)
                  for y in range(256) for x in range(256)])
    logo.save(art)
    scheme=Scheme(logo_px={'x':0,'y':0,'w':16,'h':16})
    result=selection_png.render(bag,art,scheme)
    values=[result.getpixel((x,8))[0] for x in range(2,14)]
    assert all(100<value<155 for value in values),values


def test_customer_confirmation_has_logo_and_numeric_mm_annotation_without_guides(tmp_path):
    bag = tmp_path / 'bag.png'
    logo_file = tmp_path / 'logo.png'
    Image.new('RGB', (240, 180), '#d8c3a9').save(bag)
    Image.new('RGBA', (40, 20), (0, 0, 255, 255)).save(logo_file)
    scheme = Scheme(logo_px={'x': 80, 'y': 60, 'w': 80, 'h': 40}, size_mm={'w': 50, 'h': 25})

    image = customer_export.render_confirmation(bag, logo_file, scheme)

    assert image.size == (240, 180)
    assert image.getpixel((120, 80))[:3] == (0, 0, 255)
    assert image.getpixel((0, 0))[:3] == (216, 195, 169)
    assert customer_export.annotation_text(scheme) == '50 x 25 mm'


def test_customer_confirmation_annotation_is_large_centered_and_uses_ascii_x(tmp_path):
    bag = tmp_path / 'bag.png'
    logo_file = tmp_path / 'logo.png'
    Image.new('RGB', (800, 800), '#d8c3a9').save(bag)
    Image.new('RGBA', (40, 20), (0, 0, 255, 255)).save(logo_file)
    scheme = Scheme(logo_px={'x': 360, 'y': 300, 'w': 80, 'h': 40}, size_mm={'w': 43.753, 'h': 25.791})

    image = customer_export.render_confirmation(bag, logo_file, scheme)
    font_size = customer_export.annotation_font_size(image.width)
    text = customer_export.annotation_text(scheme)
    x, y = customer_export.annotation_position(image.size, (240, font_size))

    assert text == '43.8 x 25.8 mm'
    assert font_size >= 28
    assert x == 280
    assert y == 800 - font_size - 20


def test_tinted_confirmation_uses_logo_alpha_not_original_blue_pixels(tmp_path):
    bag = tmp_path / 'bag.png'
    logo_file = tmp_path / 'logo.png'
    Image.new('RGB', (160, 100), '#d8c3a9').save(bag)
    Image.new('RGBA', (20, 10), (0, 0, 255, 255)).save(logo_file)
    scheme = Scheme(color='white', logo_px={'x': 50, 'y': 30, 'w': 40, 'h': 20}, size_mm={'w': 50, 'h': 25})

    image = customer_export.render_confirmation(bag, logo_file, scheme)

    assert image.getpixel((70, 40))[:3] == (255, 255, 255)


def test_save_dialog_returns_none_when_the_user_cancels(monkeypatch):
    class Root:
        def withdraw(self):
            pass

        def destroy(self):
            pass

    monkeypatch.setattr(save_dialog.tk, 'Tk', Root)
    monkeypatch.setattr(save_dialog.filedialog, 'asksaveasfilename', lambda **_kwargs: '')

    assert save_dialog.choose_png_destination('customer.png') is None


def test_customer_export_writes_a_named_png_to_its_task_output_without_a_native_save_dialog(client):
    project = ready_project(client)

    result = data(client.post('/api/projects/sample/customer-export', json={
        'revision': project['revision'], 'filename': 'customer-bag.png',
    }))

    assert result['version']['version_id'] == 'version-0001'
    assert result['output_path'] == 'output/customer-confirmations/version-0001-customer-bag.png'
    assert (repo.PROJECTS_DIR / 'sample' / result['output_path']).is_file()
    assert len(data(client.get('/api/projects/sample/versions'))) == 1


def test_customer_export_ignores_legacy_crop_data(client):
    project = ready_project(client)
    project['crop'] = {'x': 100, 'y': 75, 'w': 200, 'h': 150}
    project = data(client.put('/api/projects/sample', json=project))

    result = data(client.post('/api/projects/sample/customer-export', json={
        'revision': project['revision'],
    }))

    with Image.open(repo.PROJECTS_DIR / 'sample' / result['output_path']) as confirmation:
        assert confirmation.size == (400, 300)


def test_customer_export_render_failure_leaves_no_version_or_customer_png(client, monkeypatch):
    monkeypatch.setattr(customer_export, 'render_confirmation', lambda *_args: (_ for _ in ()).throw(ValueError('bad render')))
    project = ready_project(client)

    response = client.post('/api/projects/sample/customer-export', json={'revision': project['revision']})

    assert response.json()['ok'] is False
    assert data(client.get('/api/projects/sample/versions')) == []
    assert data(client.get('/api/projects/sample'))['next_version_number'] == 1
    assert not (repo.PROJECTS_DIR / 'sample' / 'output' / 'customer-confirmations').exists()


def test_version_production_export_writes_only_the_three_factory_files(client, monkeypatch):
    class Engine:
        def available(self):
            return True

        def svg_to_pdf(self, _svg, pdf, *, text_to_path=True):
            assert text_to_path is True
            Path(pdf).write_bytes(b'%PDF-1.4\nfactory test\n')

    monkeypatch.setattr(export_router, 'get_engine', lambda: Engine())
    project = ready_project(client)
    delivered = data(client.post('/api/projects/sample/customer-export', json={
        'revision': project['revision'], 'filename': 'customer.png',
    }))

    result = data(client.post(
        f"/api/projects/sample/versions/{delivered['version']['version_id']}/production-export"
    ))

    assert result['files'] == [
        'output/production/version-0001/Logo尺寸稿.svg',
        'output/production/version-0001/Logo尺寸稿.pdf',
        'output/production/version-0001/印刷定位图.png',
    ]
    output = repo.PROJECTS_DIR / 'sample'
    size_svg = (output / result['files'][0]).read_text(encoding='utf-8')
    assert size_svg.startswith('<svg')
    assert '50.0 mm' in size_svg
    assert '25.0 mm' in size_svg
    assert 'artwork' not in size_svg
    assert (output / result['files'][1]).read_bytes().startswith(b'%PDF')
    with Image.open(output / result['files'][2]) as placement:
        assert placement.size == (400, 300)
        assert placement.getpixel((70, 240))[:3] == (0, 0, 255)


def test_production_export_replaces_legacy_cached_factory_files(client, monkeypatch):
    class Engine:
        calls = 0

        def available(self):
            return True

        def svg_to_pdf(self, _svg, pdf, *, text_to_path=True):
            self.calls += 1
            Path(pdf).write_bytes(b'%PDF-1.4\nfactory test\n')

    engine = Engine()
    monkeypatch.setattr(export_router, 'get_engine', lambda: engine)
    project = ready_project(client)
    delivered = data(client.post('/api/projects/sample/customer-export', json={
        'revision': project['revision'], 'filename': 'customer.png',
    }))
    folder = repo.PROJECTS_DIR / 'sample' / 'output' / 'production' / delivered['version']['version_id']
    folder.mkdir(parents=True)
    (folder / 'Logo尺寸稿.svg').write_text(
        '<svg data-logomock-spec="source-page-v2" viewBox="0 0 100 60"/>',
        encoding='utf-8',
    )
    (folder / 'Logo尺寸稿.pdf').write_bytes(b'%PDF-1.4\nlegacy\n')
    Image.new('RGB', (10, 10), 'white').save(folder / '印刷定位图.png')

    result = data(client.post(
        f"/api/projects/sample/versions/{delivered['version']['version_id']}/production-export"
    ))

    assert engine.calls == 1
    assert 'data-logomock-spec="source-page-v3"' in (folder / 'Logo尺寸稿.svg').read_text(encoding='utf-8')
    assert result['files'][0].endswith('/Logo尺寸稿.svg')


def test_production_placement_marks_nearest_clearances_and_logo_width_height(tmp_path):
    bag = tmp_path / 'bag.png'
    logo = tmp_path / 'logo.png'
    Image.new('RGB', (800, 600), 'white').save(bag)
    Image.new('RGBA', (40, 20), (0, 0, 255, 255)).save(logo)
    frame = Frame(x=100, y=100, w=600, h=400)
    scheme = Scheme(
        logo_px={'x': 200, 'y': 300, 'w': 100, 'h': 60},
        size_mm={'w': 50, 'h': 30},
    )

    image = placement_png.render(bag, logo, frame, scheme, pixels_per_mm=2)

    red_pixels = sum(pixel[:3] == (226, 75, 74) for pixel in image.get_flattened_data())
    assert red_pixels > 100
    assert image.getpixel((400, 100))[:3] == (255, 255, 255)
    plan = placement_png.annotation_plan(frame, scheme, pixels_per_mm=2)
    assert [(item['kind'], item['label']) for item in plan] == [
        ('horizontal-clearance', '50.0 mm'),
        ('vertical-clearance', '70.0 mm'),
        ('logo-width', '50.0 mm'),
        ('logo-height', '30.0 mm'),
    ]
    assert all('距' not in item['label'] for item in plan)


def test_size_pdf_expands_the_source_viewbox_instead_of_adding_another_logo_viewport(tmp_path):
    engine = get_engine()
    if not engine.available():
        pytest.skip('Real Inkscape PDF test requires Inkscape')
    source = tmp_path / 'source.svg'
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="547.30414" height="227.47881" '
        'viewBox="0 0 547.30414 227.47881" preserveAspectRatio="xMidYMid meet" overflow="visible">'
        '<g><path id="logo" fill="#2054d8" d="M 0,0 H 117.75 V 11.25 H 0 Z" '
        'transform="matrix(1.3333333,0,0,-1.3333333,186.80828,142.40095)"/>'
        '<path fill="#2054d8" d="M 0,0 H 20 V 20 H 0 Z" '
        'style="display:none!important" transform="matrix(1.3333333,0,0,-1.3333333,198,117)"/></g></svg>',
        encoding='utf-8',
    )
    selected = ET.fromstring(svg_document.select_svg(
        svg_document.prepare_svg(source), {'logo'}, Rect(x=186.808, y=127.658, w=156.015, h=14.991)
    ))
    selected.set('x', '0')
    selected.set('y', '0')
    selected.set('width', '156.015')
    selected.set('height', '14.991')
    clean = tmp_path / 'clean.svg'
    clean.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="156.015" height="14.991" viewBox="0 0 156.015 14.991">'
        + ET.tostring(selected, encoding='unicode') + '</svg>',
        encoding='utf-8',
    )
    scheme = Scheme(size_mm={'w': 83.26, 'h': 8})
    spec = tmp_path / 'size.svg'
    pdf = tmp_path / 'size.pdf'
    png = tmp_path / 'size.png'
    content = spec_svg.build(clean, scheme)
    spec.write_text(content, encoding='utf-8')

    # A separate page SVG wrapping this already-nested source is the form that
    # Inkscape drops during PDF export. The source page itself must expand to
    # accommodate the annotations, retaining its original SVG viewport.
    output_root = ET.fromstring(content)
    assert float(output_root.get('viewBox').split()[0]) < 0

    engine.svg_to_pdf(spec, pdf)
    engine.svg_to_png(pdf, png)

    with Image.open(png).convert('RGB') as image:
        pixels_per_mm = image.width / max(105, scheme.size_mm.w + 50)
        logo = image.crop(tuple(round(value * pixels_per_mm) for value in (15, 15, 15 + scheme.size_mm.w, 15 + scheme.size_mm.h)))
        assert sum(red < 80 and green < 130 and blue > 150 for red, green, blue in logo.get_flattened_data()) > 100


def test_size_spec_uses_the_selected_vector_logo_color_and_matching_chinese_label(tmp_path):
    source = tmp_path / 'logo.svg'
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" viewBox="0 0 40 20">'
        '<path id="art" fill="#a6519b" style="fill:#a6519b;stroke:#704066" stroke="#704066" '
        'd="M 0,0 H 40 V 20 H 0 Z"/></svg>',
        encoding='utf-8',
    )

    document = spec_svg.build(source, Scheme(color='white', size_mm={'w': 40, 'h': 20}))
    art = ET.fromstring(document).find('.//*[@id="art"]')

    assert art.get('fill') == '#ffffff'
    assert art.get('stroke') == '#ffffff'
    assert 'fill:' not in art.get('style', '')
    assert '印色 白色' in document


def test_placement_labels_are_separated_from_their_dimension_lines(tmp_path):
    bag = tmp_path / 'bag.png'
    logo = tmp_path / 'logo.png'
    Image.new('RGB', (800, 600), '#252525').save(bag)
    Image.new('RGBA', (40, 20), (0, 0, 255, 255)).save(logo)
    frame = Frame(x=100, y=100, w=600, h=400)
    scheme = Scheme(logo_px={'x': 200, 'y': 300, 'w': 100, 'h': 60}, size_mm={'w': 50, 'h': 30})

    image = placement_png.render(bag, logo, frame, scheme, pixels_per_mm=2)
    layout = placement_png.dimension_layout(image, frame, scheme, pixels_per_mm=2)

    for item in layout:
        left, top, right, bottom = item['label_box']
        if item['axis'] == 'horizontal':
            assert bottom + 4 <= item['line'] or top >= item['line'] + 4
        else:
            assert right + 4 <= item['line'] or left >= item['line'] + 4
        padding = (left + 2, (top + bottom) // 2)
        assert image.convert('RGB').getpixel(padding) == (255, 255, 255)
