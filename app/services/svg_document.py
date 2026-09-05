"""Safe SVG documents and lossless object selection (no path rewriting)."""
import copy
import re
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as SafeET

from app.models import Rect

SVG = 'http://www.w3.org/2000/svg'
XLINK = 'http://www.w3.org/1999/xlink'
ET.register_namespace('',SVG)
ET.register_namespace('xlink',XLINK)
DRAWABLE = {'path','rect','circle','ellipse','line','polyline','polygon','text','image','use'}
NONRENDER = {'defs','clipPath','mask','marker','pattern','symbol','metadata','namedview','title','desc'}


def tag(element):
    return element.tag.rsplit('}',1)[-1] if isinstance(element.tag,str) else ''


def number(value):
    return format(float(value),'.12g')


def view_box(root):
    value=root.get('viewBox','').replace(',',' ').split()
    if len(value)==4:
        rect=Rect(x=float(value[0]),y=float(value[1]),w=float(value[2]),h=float(value[3]))
    else:
        factors={'':1,'px':1,'mm':96/25.4,'cm':96/2.54,'in':96,'pt':96/72,'pc':16}
        lengths=[]
        for attr in ('width','height'):
            match=re.fullmatch(r'\s*([\d.+eE-]+)\s*([a-z]*)\s*',root.get(attr,''))
            if not match or match[2] not in factors:
                raise ValueError('SVG 缺少有效的画板尺寸或 viewBox')
            lengths.append(float(match[1])*factors[match[2]])
        rect=Rect(w=lengths[0],h=lengths[1])
    if rect.w<=0 or rect.h<=0 or max(rect.w,rect.h)>1_000_000:
        raise ValueError('SVG 画板尺寸无效或过大')
    return rect


def drawable_elements(root):
    def visit(element):
        kind=tag(element)
        if kind in NONRENDER:
            return
        if kind in DRAWABLE:
            yield element
            return
        for child in element:
            yield from visit(child)
    yield from visit(root)


def prepare_svg(path):
    try:
        content=Path(path).read_bytes()
        if len(content)>40*1024*1024:
            raise ValueError('SVG 超过 40 MB')
        root=SafeET.fromstring(content,forbid_dtd=True,forbid_entities=True,forbid_external=True)
    except Exception as exc:
        raise ValueError(f'SVG 无法安全解析：{exc}') from exc
    if tag(root)!='svg':
        raise ValueError('不是 SVG 文件')
    ids=set()
    for node in root.iter():
        kind=tag(node)
        if kind in {'script','foreignObject','animate','animateMotion','animateTransform','set','discard'}:
            raise ValueError('SVG 含活动内容，请另存为纯静态 SVG')
        ident=node.get('id')
        if ident:
            if ident in ids:
                raise ValueError('SVG 含重复对象 ID，请先另存为纯 SVG')
            ids.add(ident)
        texts=[node.text or ''] if kind=='style' else []
        for key,value in node.attrib.items():
            attr=key.rsplit('}',1)[-1]
            if attr.lower().startswith('on'):
                raise ValueError('SVG 含脚本事件')
            safe_data = bool(re.match(r'^data:image/(png|jpeg|webp);base64,',value,re.I))
            safe_profile = kind=='color-profile' and value.lower().startswith('data:application/vnd.iccprofile;base64,')
            if attr=='href' and not (value.startswith('#') or safe_data or safe_profile):
                raise ValueError('SVG 引用了外部文件，请先嵌入图片后重试')
            texts.append(value)
        for text in texts:
            if '@import' in text.lower() or re.search(r'url\(\s*[\"\']?(?!#)[^\s\"\']',text,re.I) or '\\' in text:
                raise ValueError('SVG 含外部或不支持的样式引用，请先展开样式')
    for i,node in enumerate(drawable_elements(root)):
        if not node.get('id'):
            ident=f'lm-object-{i}'
            while ident in ids:
                ident+='x'
            node.set('id',ident)
            ids.add(ident)
    if len(list(drawable_elements(root)))>3000:
        raise ValueError('SVG 对象超过 3000 个，请先精简或按 Logo 拆分')
    box=view_box(root)
    root.set('viewBox',' '.join(number(v) for v in (box.x,box.y,box.w,box.h)))
    root.set('width',number(box.w))
    root.set('height',number(box.h))
    # 1 viewport pixel = 1 source viewBox user unit during bbox analysis.
    root.set('preserveAspectRatio','xMidYMid meet')
    return root


def serialize(root):
    return ET.tostring(root,encoding='unicode',xml_declaration=False)


def prefix_ids(root, prefix):
    """Copy an SVG page and namespace every local id/reference for composition."""
    result = copy.deepcopy(root)
    id_map = {node.get('id'): prefix + node.get('id') for node in result.iter() if node.get('id')}

    def rewrite_urls(value):
        return re.sub(
            r'url\(\s*(["\']?)#([^\s"\')]+)\1\s*\)',
            lambda match: 'url(#' + id_map.get(match[2], match[2]) + ')',
            value,
        )

    for node in result.iter():
        for key, value in list(node.attrib.items()):
            attr = key.rsplit('}', 1)[-1]
            if attr == 'id':
                node.set(key, id_map[value])
            elif attr == 'href' and value.startswith('#'):
                node.set(key, '#' + id_map.get(value[1:], value[1:]))
            else:
                node.set(key, rewrite_urls(value))
        if tag(node) == 'style' and node.text:
            text = rewrite_urls(node.text)
            for old, new in id_map.items():
                text = re.sub(r'#' + re.escape(old) + r'(?![\w-])', '#' + new, text)
            node.text = text
    return result


def candidate_seed_ids(root):
    """Return document-order non-overlapping drawable groups, preferring source <g>s."""
    claimed = set()
    seeds = []

    def descendants(node):
        kind = tag(node)
        if kind in NONRENDER:
            return
        if kind in DRAWABLE:
            ident = node.get('id')
            if ident:
                yield ident
            return
        for child in node:
            yield from descendants(child)

    def group_label(node):
        for key, value in node.attrib.items():
            if key.rsplit('}', 1)[-1] == 'label' and value:
                return value
        ident = node.get('id', '')
        return ident.rsplit('--', 1)[-1] if ident else ''

    def visit(node):
        for child in node:
            visit(child)
        if tag(node) != 'g':
            return
        available = [ident for ident in descendants(node) if ident not in claimed]
        if len(available) >= 2:
            seeds.append((group_label(node), available))
            claimed.update(available)

    visit(root)
    for ident in descendants(root):
        if ident not in claimed:
            seeds.append(('', [ident]))
    return seeds


def select_svg(root, selected_ids, box):
    result=copy.deepcopy(root)
    available={n.get('id') for n in drawable_elements(result)}
    if not selected_ids or not set(selected_ids)<=available:
        raise ValueError('请选择有效的 Logo 对象')
    # Keep a pristine, inert reference tree for <use>, including referenced groups.
    # Hiding a definition itself changes every clone that references it.
    uses=[node for node in result.iter() if tag(node)=='use']
    if uses:
        reference=copy.deepcopy(root)
        prefix='lm-ref-'+uuid.uuid4().hex+'-'
        id_map={node.get('id'):prefix+node.get('id') for node in reference.iter() if node.get('id')}

        def urls(value):
            return re.sub(r'url\(\s*([\"\']?)#([^\s\"\')]+)\1\s*\)',
                          lambda match:'url(#'+id_map.get(match[2],match[2])+')',value)

        for node in reference.iter():
            for key,value in list(node.attrib.items()):
                attr=key.rsplit('}',1)[-1]
                if attr=='id':
                    node.set(key,id_map[value])
                elif attr=='href' and value.startswith('#'):
                    node.set(key,'#'+id_map.get(value[1:],value[1:]))
                else:
                    node.set(key,urls(value))
            if tag(node)=='style' and node.text:
                text=urls(node.text)
                def selector(match):
                    head=match[1]
                    for old,new in id_map.items():
                        head=re.sub(r'#'+re.escape(old)+r'(?![\w-])','#'+new,head)
                    return head+'{'
                node.text=re.sub(r'([^{}]+)\{',selector,text)
        for use in uses:
            for key in ('href',f'{{{XLINK}}}href'):
                value=use.get(key,'')
                if value.startswith('#') and value[1:] in id_map:
                    use.set(key,'#'+id_map[value[1:]])
        definitions=ET.Element(f'{{{SVG}}}defs')
        definitions.append(reference)
        result.insert(0,definitions)
    for node in drawable_elements(result):
        if node.get('id') not in selected_ids:
            node.set('display','none')
            node.set('style',node.get('style','')+';display:none!important')
    original=view_box(root)
    result.set('x',number(original.x))
    result.set('y',number(original.y))
    # Preserve percentages and other viewport-relative units inside the original SVG.
    result.set('overflow','visible')
    cropped=ET.Element(f'{{{SVG}}}svg',width=number(box.w),height=number(box.h),
                       viewBox=' '.join(number(v) for v in (box.x,box.y,box.w,box.h)))
    cropped.append(result)
    return serialize(cropped)


def embedded_logo(path,x,y,w,h):
    root=prepare_svg(path)
    root.set('x',number(x))
    root.set('y',number(y))
    root.set('width',number(w))
    root.set('height',number(h))
    root.set('overflow','hidden')
    return serialize(root)
