import base64
from xml.etree import ElementTree as ET

from PIL import Image

from app.models import Scheme,Rect,Frame
from app.services import customer_export, placement_svg, save_dialog, selection_png, spec_svg

NS='{http://www.w3.org/2000/svg}'


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


def test_clean_png_has_no_frames_badges_or_labels_and_crop_is_independent(tmp_path):
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
    crop=selection_png.render(bag,art,scheme,Rect(x=20,y=10,w=60,h=50))
    assert crop.size==(60,50)
    assert crop.getpixel((30,25))[:3]==(0,0,255)


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

    image = customer_export.render_confirmation(bag, logo_file, scheme, None)

    assert image.size == (240, 180)
    assert image.getpixel((120, 80))[:3] == (0, 0, 255)
    assert image.getpixel((0, 0))[:3] == (216, 195, 169)
    assert customer_export.annotation_text(scheme) == '50 × 25 mm'


def test_tinted_confirmation_uses_logo_alpha_not_original_blue_pixels(tmp_path):
    bag = tmp_path / 'bag.png'
    logo_file = tmp_path / 'logo.png'
    Image.new('RGB', (160, 100), '#d8c3a9').save(bag)
    Image.new('RGBA', (20, 10), (0, 0, 255, 255)).save(logo_file)
    scheme = Scheme(color='white', logo_px={'x': 50, 'y': 30, 'w': 40, 'h': 20}, size_mm={'w': 50, 'h': 25})

    image = customer_export.render_confirmation(bag, logo_file, scheme, None)

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
