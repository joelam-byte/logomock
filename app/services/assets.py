"""Reversible logo cleanup, object grouping and immutable clean asset versions."""
import base64
import io
import re
import shutil
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from app.engine.base import EngineError
from app.models import Asset, AssetObject, AssetPage, Candidate, Rect
from app.services.pdf_pages import page_count
from app.services import svg_document as svg
from app.services.raster_assets import clean_raster, component_images


def union_box(boxes):
    boxes=list(boxes)
    if not boxes:
        raise ValueError('没有可用的图形边界')
    x=min(b.x for b in boxes)
    y=min(b.y for b in boxes)
    return Rect(x=x,y=y,w=max(b.x+b.w for b in boxes)-x,h=max(b.y+b.h for b in boxes)-y)


def area(box):
    return box.w*box.h


def overlap(a,b):
    return max(0,min(a.x+a.w,b.x+b.w)-max(a.x,b.x))*max(0,min(a.y+a.h,b.y+b.h)-max(a.y,b.y))


def classify_objects(items,page):
    objects=[]
    for index,item in enumerate(items):
        box=Rect.model_validate(item['box'])
        reason=item.get('reason')
        if not reason and index==0 and len(items)>1 and overlap(box,page)>=area(page)*0.97:
            reason='background'
        text=item.get('text','').strip()
        if re.search(r'\d\s*(?:mm|cm|毫米|厘米|inch|in\b)',text,re.I):
            reason='dimension'
        objects.append(AssetObject(id=item['id'],label=item.get('label') or item['id'],box=box,reason=reason,selected=not reason))
    metadata={item['id']:item for item in items}
    dimension_paints=set()
    for obj in objects:
        box=obj.box
        item=metadata[obj.id]
        thin=max(box.w,box.h)>max(0.1,min(box.w,box.h))*8
        supports=sum(1 for other in objects if other is not obj and other.selected
                     and not metadata[other.id].get('straight')
                     and overlap(box,other.box)>max(area(box),0.01)*0.5)
        if obj.selected and thin and item.get('straight') and supports<=2:
            obj.reason='dimension'
            obj.selected=False
        if obj.reason=='dimension' and item.get('stroke') not in (None,'none'):
            dimension_paints.add(item['stroke'])
    for obj in objects:
        item=metadata[obj.id]
        # Outlined labels scattered across a page have sparse ink in a large bbox.
        # Require a matching, independently detected dimension-line color too.
        if obj.selected and item.get('alpha_occupancy',1)<0.10 and item.get('fill') in dimension_paints:
            obj.reason='dimension'
            obj.selected=False
    return objects


def group_candidates(objects):
    remaining=[obj for obj in objects if obj.selected and obj.box.w>0 and obj.box.h>0]
    if not remaining:
        return []
    whole=union_box(obj.box for obj in remaining)
    gap=max(1,min(whole.w,whole.h)*0.05)
    groups=[]
    while remaining:
        group=[remaining.pop(0)]
        queue=list(group)
        while queue:
            box=queue.pop().box
            for other in remaining[:]:
                b=other.box
                dx=max(b.x-(box.x+box.w),box.x-(b.x+b.w),0)
                dy=max(b.y-(box.y+box.h),box.y-(b.y+b.h),0)
                if dx<=gap and dy<=gap:
                    remaining.remove(other)
                    group.append(other)
                    queue.append(other)
        groups.append(group)
    groups.sort(key=lambda group:area(union_box(obj.box for obj in group)),reverse=True)
    return [Candidate(id=f'candidate-{index+1}',label=f'候选 Logo {index+1}',
                      object_ids=[obj.id for obj in group],box=union_box(obj.box for obj in group))
            for index,group in enumerate(groups)]


def group_page_candidates(root, objects, *, page_id, page_number):
    """Create generic, non-overlapping page candidates from source groups and hints."""
    by_id = {obj.id: obj for obj in objects}
    candidates = []
    consumed = set()
    group_number = 0
    object_number = 0

    def append(label, members):
        nonlocal group_number
        if not members:
            return
        group_number += 1
        candidates.append(Candidate(
            id=f'{page_id}--candidate-{group_number}',
            label=label or f'组 {group_number}',
            object_ids=[obj.id for obj in members],
            box=union_box(obj.box for obj in members),
        ))

    for source_label, identifiers in svg.candidate_seed_ids(root):
        members = [by_id[ident] for ident in identifiers if ident in by_id]
        normal = [obj for obj in members if obj.reason is None]
        hinted = [obj for obj in members if obj.reason in {'background', 'dimension'}]
        append(source_label, normal)
        for obj in hinted:
            object_number += 1
            append(f'对象 {object_number}', [obj])
        consumed.update(obj.id for obj in members)

    leftovers = [obj for obj in objects if obj.id not in consumed]
    for candidate in group_candidates(leftovers):
        append('', [by_id[ident] for ident in candidate.object_ids])
    return AssetPage(
        id=page_id,
        number=page_number,
        label=f'页面 {page_number}',
        objects=objects,
        candidates=candidates,
    )


def _raster_source(image):
    original=image.convert('RGBA')
    clean,components=clean_raster(original)
    if not components:
        raise ValueError('图片中没有检测到 Logo，背景与图形可能颜色太接近')
    if len(components)>1500:
        raise ValueError('图片包含过多噪点，请使用更清晰的 Logo 或矢量文件')
    root=ET.Element(f'{{{svg.SVG}}}svg',width=str(image.width),height=str(image.height),viewBox=f'0 0 {image.width} {image.height}')
    items=[]

    def append(image_,ident,box,label,reason=None):
        buffer=io.BytesIO()
        image_.save(buffer,format='PNG')
        ET.SubElement(root,f'{{{svg.SVG}}}image',id=ident,x=str(box['x']),y=str(box['y']),width=str(box['w']),height=str(box['h']),href='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii'))
        items.append(dict(id=ident,box=box,label=label,reason=reason))

    from PIL import ImageChops
    removed=original.copy()
    removed.putalpha(ImageChops.subtract(original.getchannel('A'),clean.getchannel('A')))
    if removed.getbbox():
        append(removed,'raster-background',dict(x=0,y=0,w=image.width,h=image.height),'检测到的边缘背景','background')
    for component,tile in component_images(clean,components):
        append(tile,component['id'],component['box'],component['label'])
    return root,items


def raster_preview(root,path,width=1400):
    box=svg.view_box(root)
    factor=min(1,width/max(box.w,box.h))
    canvas=Image.new('RGBA',(max(1,round(box.w*factor)),max(1,round(box.h*factor))))
    for node in svg.drawable_elements(root):
        if svg.tag(node)!='image' or node.get('display')=='none':
            continue
        href=node.get('href') or node.get(f'{{{svg.XLINK}}}href')
        with Image.open(io.BytesIO(base64.b64decode(href.split(',',1)[1]))) as tile:
            size=(max(1,round(float(node.get('width'))*factor)),max(1,round(float(node.get('height'))*factor)))
            layer=tile.convert('RGBA').resize(size,Image.Resampling.LANCZOS)
        canvas.alpha_composite(layer,(round((float(node.get('x','0'))-box.x)*factor),round((float(node.get('y','0'))-box.y)*factor)))
    canvas.save(path)


def render_preview(path,png,engine,kind,width=1400):
    if kind=='raster':
        raster_preview(svg.prepare_svg(path),png,width)
    else:
        box=svg.view_box(svg.prepare_svg(path))
        engine.svg_to_png(path,png,width=max(1,min(width,width*box.w/box.h)))


def analyze(source,folder,engine,project_root):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=False)
    source=Path(source)
    relative=lambda path:Path(path).relative_to(project_root).as_posix()
    kind='raster' if source.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} else 'vector'
    warnings=['自动清理是可恢复的建议：请核对 Logo、标注、背景与分离图形，尤其是已转曲的尺寸文字。']
    if kind=='raster':
        from app.routers.upload import image_from_bytes
        root,items=_raster_source(image_from_bytes(source.read_bytes()))
        warnings.append('此素材是位图：只清理边缘连通的纯色背景，不会变成真正的矢量；白色内部区域予以保留。')
    else:
        if not engine.available():
            from app.engine.base import EngineError
            raise EngineError('ENGINE_NOT_FOUND','分析 SVG / AI / PDF 需要 Inkscape，请先在设置中配置')
        if source.suffix.lower()!='.svg':
            converted=folder/'converted.svg'
            engine.to_svg(source,converted)
            source=converted
            warnings.append('AI / PDF 默认导入第一页；请核对所需内容和字体，有多页时先按页另存。')
        root=svg.prepare_svg(source)
        items=None
    source_svg=folder/'source.svg'
    source_svg.write_text(svg.serialize(root),encoding='utf-8')
    page=svg.view_box(root)
    if items is None:
        boxes=engine.query_all(source_svg)
        items=[]
        for element in svg.drawable_elements(root):
            ident=element.get('id')
            if ident not in boxes:
                continue
            x,y,w,h=boxes[ident]
            if w<=0 or h<=0:
                continue
            text=''.join(element.itertext()).strip()
            styles=dict(part.split(':',1) for part in element.get('style','').split(';') if ':' in part)
            styles={k.strip():v.strip() for k,v in styles.items()}
            commands=re.findall(r'[a-df-zA-DF-Z]',element.get('d',''))
            straight=svg.tag(element)=='line' or (svg.tag(element)=='path' and bool(commands) and all(c.lower() in 'mlhvz' for c in commands))
            items.append(dict(id=ident,label=text[:60] or f'{svg.tag(element)} · {ident}',text=text,tag=svg.tag(element),
                              straight=straight,fill=styles.get('fill',element.get('fill','#000000')),stroke=styles.get('stroke',element.get('stroke','none')),
                              compound=sum(c.lower()=='m' for c in commands)>=4,
                              box=dict(x=x+page.x,y=y+page.y,w=w,h=h)))
        preliminary=classify_objects(items,page)
        dimension_colors={items[i]['stroke'] for i,obj in enumerate(preliminary) if obj.reason=='dimension'}
        for item in items:
            if not item['compound'] or item['fill'] not in dimension_colors:
                continue
            bounds=Rect.model_validate(item['box'])
            probe=folder/f"probe-{uuid.uuid4().hex}.svg"
            probe.write_text(svg.select_svg(root,{item['id']},bounds),encoding='utf-8')
            render_preview(probe,probe.with_suffix('.png'),engine,'vector',width=512)
            with Image.open(probe.with_suffix('.png')) as image:
                histogram=image.convert('RGBA').getchannel('A').histogram()
                item['alpha_occupancy']=sum(histogram[16:])/(image.width*image.height)
    objects=classify_objects(items,page)
    candidates=group_candidates(objects)
    if not candidates:
        # Never silently erase an entire artwork because a heuristic was uncertain.
        for obj in objects:
            if obj.reason!='background':
                obj.reason=None
                obj.selected=True
        candidates=group_candidates(objects)
    if not candidates:
        raise ValueError('未发现可用 Logo 图形，请检查文件')
    if len(candidates)>30:
        warnings.append('发现很多分离图形；候选缩略图只显示前 30 组，其余仍可在对象列表勾选。')
    candidates=candidates[:30]
    preview=folder/'source.png'
    render_preview(source_svg,preview,engine,kind)
    for candidate in candidates:
        candidate_svg=folder/f'{candidate.id}.svg'
        candidate_svg.write_text(svg.select_svg(root,set(candidate.object_ids),candidate.box),encoding='utf-8')
        candidate_png=candidate_svg.with_suffix('.png')
        render_preview(candidate_svg,candidate_png,engine,kind,width=320)
        candidate.preview=relative(candidate_png)
    chosen=candidates[0]
    selected=set(chosen.object_ids)
    # Mark the actual suggested initial selection, not all non-background objects.
    for obj in objects:
        obj.selected=obj.id in selected
    if len(candidates)>1:
        warnings.append(f'发现 {len(candidates)} 组分离图形，暂选最大一组；可组合多个候选，避免漏掉文字或附属图形。')
    return Asset(id=uuid.uuid4().hex,source_svg=relative(source_svg),source_preview=relative(preview),kind=kind,
                 width=chosen.box.w,height=chosen.box.h,source_box=page,objects=objects,candidates=candidates,
                 selected_ids=chosen.object_ids,warnings=warnings)


def _vector_objects(root, source_svg, engine, page, folder):
    boxes = engine.query_all(source_svg)
    items = []
    for element in svg.drawable_elements(root):
        ident = element.get('id')
        if ident not in boxes:
            continue
        x, y, w, h = boxes[ident]
        if w <= 0 or h <= 0:
            continue
        text = ''.join(element.itertext()).strip()
        styles = dict(part.split(':', 1) for part in element.get('style', '').split(';') if ':' in part)
        styles = {key.strip(): value.strip() for key, value in styles.items()}
        commands = re.findall(r'[a-df-zA-DF-Z]', element.get('d', ''))
        straight = svg.tag(element) == 'line' or (
            svg.tag(element) == 'path' and bool(commands) and all(command.lower() in 'mlhvz' for command in commands)
        )
        items.append(dict(
            id=ident,
            label=text[:60] or f'{svg.tag(element)} · {ident.rsplit("--", 1)[-1]}',
            text=text,
            tag=svg.tag(element),
            straight=straight,
            fill=styles.get('fill', element.get('fill', '#000000')),
            stroke=styles.get('stroke', element.get('stroke', 'none')),
            compound=sum(command.lower() == 'm' for command in commands) >= 4,
            box=dict(x=x + page.x, y=y + page.y, w=w, h=h),
        ))
    preliminary = classify_objects(items, page)
    dimension_colors = {items[index]['stroke'] for index, obj in enumerate(preliminary) if obj.reason == 'dimension'}
    for item in items:
        if not item['compound'] or item['fill'] not in dimension_colors:
            continue
        bounds = Rect.model_validate(item['box'])
        probe = folder / f'probe-{uuid.uuid4().hex}.svg'
        probe.write_text(svg.select_svg(root, {item['id']}, bounds), encoding='utf-8')
        render_preview(probe, probe.with_suffix('.png'), engine, 'vector', width=512)
        with Image.open(probe.with_suffix('.png')) as image:
            histogram = image.convert('RGBA').getchannel('A').histogram()
            item['alpha_occupancy'] = sum(histogram[16:]) / (image.width * image.height)
    return classify_objects(items, page)


def _candidate_previews(page, root, source_svg, engine, project_root, kind):
    relative = lambda path: Path(path).relative_to(project_root).as_posix()
    for candidate in page.candidates:
        candidate_svg = Path(source_svg).with_name(f'{candidate.id}.svg')
        candidate_svg.write_text(svg.select_svg(root, set(candidate.object_ids), candidate.box), encoding='utf-8')
        candidate_png = candidate_svg.with_suffix('.png')
        render_preview(candidate_svg, candidate_png, engine, kind, width=320)
        candidate.preview = relative(candidate_png)


def analyse_svg_page(page_svg, engine, project_root, page_id, number):
    """Analyse one converted vector page and persist its page/candidate previews."""
    page_svg = Path(page_svg)
    root = svg.prefix_ids(svg.prepare_svg(page_svg), f'{page_id}--')
    page_svg.write_text(svg.serialize(root), encoding='utf-8')
    source_box = svg.view_box(root)
    objects = _vector_objects(root, page_svg, engine, source_box, page_svg.parent)
    page = group_page_candidates(root, objects, page_id=page_id, page_number=number)
    if not page.candidates:
        raise ValueError('未发现可用 Logo 图形，请检查文件')
    preview = page_svg.with_suffix('.png')
    render_preview(page_svg, preview, engine, 'vector')
    page.source_svg = page_svg.relative_to(project_root).as_posix()
    page.source_preview = preview.relative_to(project_root).as_posix()
    page.source_box = source_box
    _candidate_previews(page, root, page_svg, engine, project_root, 'vector')
    return page


def _analyse_raster_page(source, page_svg, engine, project_root, page_id):
    from app.routers.upload import image_from_bytes

    root, items = _raster_source(image_from_bytes(Path(source).read_bytes()))
    root = svg.prefix_ids(root, f'{page_id}--')
    for item in items:
        item['id'] = f'{page_id}--{item["id"]}'
    page_svg = Path(page_svg)
    page_svg.write_text(svg.serialize(root), encoding='utf-8')
    source_box = svg.view_box(root)
    objects = classify_objects(items, source_box)
    page = group_page_candidates(root, objects, page_id=page_id, page_number=1)
    if not page.candidates:
        raise ValueError('图片中没有检测到可用 Logo')
    preview = page_svg.with_suffix('.png')
    render_preview(page_svg, preview, engine, 'raster')
    page.source_svg = page_svg.relative_to(project_root).as_posix()
    page.source_preview = preview.relative_to(project_root).as_posix()
    page.source_box = source_box
    _candidate_previews(page, root, page_svg, engine, project_root, 'raster')
    return page


def analyse_source(source, folder, engine, project_root):
    """Read every available source page while retaining a visible error for each failure."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    source = Path(source)
    kind = 'raster' if source.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} else 'vector'
    warnings = ['自动清理是可恢复的建议：请核对 Logo、标注、背景与分离图形，尤其是已转曲的尺寸文字。']
    if kind == 'raster':
        warnings.append('此素材是位图：只清理边缘连通的纯色背景，不会变成真正的矢量；白色内部区域予以保留。')
        pages = [_analyse_raster_page(source, folder / 'page-0001.svg', engine, project_root, 'page-0001')]
    else:
        if not engine.available():
            raise EngineError('ENGINE_NOT_FOUND', '分析 SVG / AI / PDF 需要 Inkscape，请先在设置中配置')
        count = page_count(source) if source.suffix.lower() in {'.pdf', '.ai'} else 1
        pages = []
        for number in range(1, count + 1):
            page_id = f'page-{number:04d}'
            page_svg = folder / f'{page_id}.svg'
            try:
                if source.suffix.lower() == '.svg':
                    shutil.copy2(source, page_svg)
                else:
                    engine.to_svg_page(source, page_svg, number)
                pages.append(analyse_svg_page(page_svg, engine, project_root, page_id, number))
            except (ValueError, EngineError) as exc:
                pages.append(AssetPage(id=page_id, number=number, label=f'页面 {number}', error=f'第 {number} 页无法读取：{exc}'))
    first = next((page for page in pages if page.candidates), None)
    if first is None:
        raise ValueError('没有可用的 Logo 内容，请检查源文件或 Inkscape 设置')
    chosen = first.candidates[0]
    for page in pages:
        for obj in page.objects:
            obj.selected = obj.id in chosen.object_ids
    if sum(len(page.candidates) for page in pages) > 1:
        warnings.append('发现多个候选内容，暂选第一个候选；可组合多个候选，避免漏掉文字或附属图形。')
    return Asset(
        id=uuid.uuid4().hex,
        kind=kind,
        pages=pages,
        selected_candidate_ids=[chosen.id],
        selected_ids=list(chosen.object_ids),
        width=chosen.box.w,
        height=chosen.box.h,
        warnings=warnings,
    )


def apply_candidates(asset, candidate_ids, project_root, engine):
    """Compose only server-known candidate objects into one clean SVG and PNG."""
    if not isinstance(candidate_ids, list) or not candidate_ids or any(not isinstance(item, str) for item in candidate_ids):
        raise ValueError('请选择一个或多个有效候选内容')
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError('候选内容不能重复选择')
    candidates = {candidate.id: (page, candidate) for page in asset.pages for candidate in page.candidates}
    if not set(candidate_ids) <= candidates.keys():
        raise ValueError('请选择一个或多个有效候选内容')
    selected_by_page = {}
    selected_ids = []
    boxes = []
    for candidate_id in candidate_ids:
        page, candidate = candidates[candidate_id]
        selected_by_page.setdefault(page.id, []).extend(candidate.object_ids)
        selected_ids.extend(candidate.object_ids)
        boxes.append(candidate.box)
    bounds = union_box(boxes)
    if min(bounds.w, bounds.h) <= 0:
        raise ValueError('Logo 的宽、高必须大于零')
    token = uuid.uuid4().hex
    target_parent = Path(project_root) / Path(asset.pages[0].source_svg).parent
    target = target_parent / f'clean-{token}.svg'
    composed = ET.Element(
        f'{{{svg.SVG}}}svg',
        width=svg.number(bounds.w),
        height=svg.number(bounds.h),
        viewBox=f'0 0 {svg.number(bounds.w)} {svg.number(bounds.h)}',
    )
    for page in asset.pages:
        identifiers = selected_by_page.get(page.id)
        if not identifiers:
            continue
        if not page.source_svg or not page.source_box:
            raise ValueError('所选页面无法读取')
        root = svg.prepare_svg(Path(project_root) / page.source_svg)
        page_bounds = union_box(obj.box for obj in page.objects if obj.id in set(identifiers))
        fragment = ET.fromstring(svg.select_svg(root, set(identifiers), page_bounds))
        fragment.set('x', svg.number(page_bounds.x - bounds.x))
        fragment.set('y', svg.number(page_bounds.y - bounds.y))
        fragment.set('width', svg.number(page_bounds.w))
        fragment.set('height', svg.number(page_bounds.h))
        composed.append(fragment)
    target.write_text(svg.serialize(composed), encoding='utf-8')
    preview = target.with_suffix('.png')
    render_preview(target, preview, engine, asset.kind, width=2048)
    result = asset.model_copy(deep=True)
    result.id = token
    result.width = bounds.w
    result.height = bounds.h
    result.selected_candidate_ids = list(candidate_ids)
    result.selected_ids = selected_ids
    for page in result.pages:
        for obj in page.objects:
            obj.selected = obj.id in selected_ids
    return result, target.relative_to(project_root).as_posix(), preview.relative_to(project_root).as_posix()


def apply_selection(asset,selected_ids,project_root,engine):
    ids=set(selected_ids)
    allowed={obj.id for obj in asset.objects}
    if not ids or not ids<=allowed:
        raise ValueError('至少勾选一个有效对象；不能选择其他素材的对象')
    bounds=union_box(obj.box for obj in asset.objects if obj.id in ids)
    if min(bounds.w,bounds.h)<=0:
        raise ValueError('Logo 的宽、高必须大于零')
    root=svg.prepare_svg(Path(project_root)/asset.source_svg)
    token=uuid.uuid4().hex
    target=Path(project_root)/Path(asset.source_svg).parent/f'clean-{token}.svg'
    target.write_text(svg.select_svg(root,ids,bounds),encoding='utf-8')
    preview=target.with_suffix('.png')
    render_preview(target,preview,engine,asset.kind,width=2048)
    result=asset.model_copy(deep=True)
    result.id=token
    result.width=bounds.w
    result.height=bounds.h
    result.selected_ids=[obj.id for obj in result.objects if obj.id in ids]
    for obj in result.objects:
        obj.selected=obj.id in ids
    return result,target.relative_to(project_root).as_posix(),preview.relative_to(project_root).as_posix()
