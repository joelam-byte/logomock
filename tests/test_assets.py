from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image, ImageDraw

from app.models import Rect
from app.services.svg_document import prepare_svg, select_svg
from app.services.assets import classify_objects, group_candidates
from app.services.raster_assets import clean_raster

NS = '{http://www.w3.org/2000/svg}'


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
