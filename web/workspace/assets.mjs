import {el,button,dialog,dialogError,closeDialog} from './ui.mjs';
import {fileURL} from './persistence.mjs';
import {svgNode} from './editor.mjs';

export class SelectionReview {
 constructor(ids,onChange=()=>{}){this.selected=new Set(ids);this.applying=false;this.onChange=onChange;}
 update(change){if(this.applying)return false;change(this.selected);this.onChange();return true;}
 async apply(work){
  if(this.applying)throw Object.assign(new Error('清理结果正在应用，请等待完成。'),{code:'OPERATION_BUSY'});
  this.applying=true;
  try{this.onChange();return await work([...this.selected]);}finally{this.applying=false;this.onChange();}
 }
}

export function mergeCandidateIds(selected, candidateId) {
 const next=new Set(selected);
 if(next.has(candidateId))next.delete(candidateId);else next.add(candidateId);
 return next;
}

export function pageSelections(asset) {
 const selected=new Set(asset?.selected_candidate_ids||[]);
 return new Map((asset?.pages||[]).map(page=>[
  page.id,
  new Set((page.candidates||[]).filter(candidate=>selected.has(candidate.id)).map(candidate=>candidate.id)),
 ]));
}

export function selectionForPage(selections,pageId) {
 return new Set(selections.get(pageId)||[]);
}

export function togglePageCandidate(selections,pageId,candidateId) {
 const next=new Map([...selections].map(([id,selected])=>[id,new Set(selected)]));
 const selected=next.get(pageId)||new Set();
 if(selected.has(candidateId))selected.delete(candidateId);else selected.add(candidateId);
 next.set(pageId,selected);
 return next;
}

export function candidatesForPage(page,selected) {
 return (page?.candidates||[]).filter(candidate=>selected.has(candidate.id));
}

export function candidatesIntersecting(candidates,rect) {
 return candidates.filter(candidate=>{
  const box=candidate.box;
  return box.x<rect.x+rect.w&&box.x+box.w>rect.x&&box.y<rect.y+rect.h&&box.y+box.h>rect.y;
 });
}

export function previewLayout(candidates,viewport) {
 if(!candidates.length)return {bounds:null,items:[]};
 const left=Math.min(...candidates.map(candidate=>candidate.box.x));
 const top=Math.min(...candidates.map(candidate=>candidate.box.y));
 const right=Math.max(...candidates.map(candidate=>candidate.box.x+candidate.box.w));
 const bottom=Math.max(...candidates.map(candidate=>candidate.box.y+candidate.box.h));
 const bounds={x:left,y:top,w:right-left,h:bottom-top};
 const available={w:Math.max(1,viewport.width-24),h:Math.max(1,viewport.height-24)};
 const scale=Math.min(available.w/bounds.w,available.h/bounds.h);
 const offset={x:(viewport.width-bounds.w*scale)/2,y:(viewport.height-bounds.h*scale)/2};
 return {bounds,scale,items:candidates.map(candidate=>({
  id:candidate.id,
  x:offset.x+(candidate.box.x-bounds.x)*scale,
  y:offset.y+(candidate.box.y-bounds.y)*scale,
  w:candidate.box.w*scale,
  h:candidate.box.h*scale,
 }))};
}

export function pickerReady(selected) {
 return selected.size>0;
}

export function logoPickerDialog(project,applyCandidateIds) {
 const asset=project.asset;
 if(!asset)return;
 const pages=asset.pages||[];
 const first=pages.find(page=>!page.error&&page.candidates?.length);
 if(!first)return;
 let activePageId=first.id;
 let selections=pageSelections(asset);
 let applying=false;
 let previewToken=0;
 let drag=null;
 const root=dialog('选择 Logo 内容',{canClose:()=>!applying});
 const grid=el('div','logo-picker-grid');
 const pagesColumn=el('section','picker-pages');
 const sourceColumn=el('section','picker-source');
 const previewColumn=el('section','picker-preview');
 const pageList=el('div','picker-page-list');
 const sourceStage=el('div','picker-source-stage');
 const sourceCanvas=svgNode('svg');
 sourceCanvas.classList.add('picker-source-canvas');
 sourceCanvas.setAttribute('aria-label','当前页面 Logo 内容选择画布');
 const sourceStatus=el('p','picker-source-status');
 const count=el('p','muted');
 const preview=el('canvas','picker-preview-canvas');
 preview.width=480;
 preview.height=250;
 pagesColumn.append(el('h3','','页面'),pageList);
 sourceStage.append(sourceCanvas);
 sourceColumn.append(el('h3','','页面内容'),sourceStage,sourceStatus);
 previewColumn.append(el('h3','','已选预览'),count,preview);
 grid.append(pagesColumn,sourceColumn,previewColumn);
 root.append(grid);
 const footer=el('div','dialog-footer');
 const submit=button('确认使用',async()=>{
  const selected=selectionForPage(selections,activePageId);
  if(applying||!pickerReady(selected))return;
  applying=true;render();
  try{await applyCandidateIds([...selected]);closeDialog();}catch(error){dialogError(root,error);}finally{applying=false;render();}
 },'primary');
 footer.append(button('取消',closeDialog),submit);root.append(footer);

 function currentPage(){return pages.find(page=>page.id===activePageId)||first;}
 function currentSelection(){return selectionForPage(selections,currentPage().id);}
 function selectedCandidates(){return candidatesForPage(currentPage(),currentSelection());}
 function addCandidates(candidates){
  if(!candidates.length)return;
  const page=currentPage(),next=new Map([...selections].map(([id,selected])=>[id,new Set(selected)]));
  const selected=selectionForPage(next,page.id);
  for(const candidate of candidates)selected.add(candidate.id);
  next.set(page.id,selected);
  selections=next;
 }
 function sourcePoint(event){
  const point=sourceCanvas.createSVGPoint();
  point.x=event.clientX;point.y=event.clientY;
  return point.matrixTransform(sourceCanvas.getScreenCTM().inverse());
 }
 function sourceRect(start,end){
  return {x:Math.min(start.x,end.x),y:Math.min(start.y,end.y),w:Math.abs(end.x-start.x),h:Math.abs(end.y-start.y)};
 }
 function candidateAt(point){
  return (currentPage().candidates||[])
   .filter(candidate=>point.x>=candidate.box.x&&point.x<=candidate.box.x+candidate.box.w&&point.y>=candidate.box.y&&point.y<=candidate.box.y+candidate.box.h)
   .sort((a,b)=>a.box.w*a.box.h-b.box.w*b.box.h)[0]||null;
 }
 function drawSource(){
  const page=currentPage(),box=page.source_box;
  sourceCanvas.replaceChildren();
  if(!box)return;
  sourceCanvas.setAttribute('viewBox',`${box.x} ${box.y} ${box.w} ${box.h}`);
  sourceCanvas.append(svgNode('image',{href:fileURL(project,page.source_preview),x:box.x,y:box.y,width:box.w,height:box.h,preserveAspectRatio:'none'}));
  const selected=currentSelection();
  for(const candidate of page.candidates||[]){
   const chosen=selected.has(candidate.id);
   const overlay=svgNode('rect',{x:candidate.box.x,y:candidate.box.y,width:candidate.box.w,height:candidate.box.h,fill:chosen?'#27664c22':'transparent',stroke:chosen?'#27664c':'transparent','stroke-width':1.4,'vector-effect':'non-scaling-stroke'});
   overlay.classList.add('picker-source-candidate');
   sourceCanvas.append(overlay);
  }
  if(drag?.pageId===page.id&&drag.current){
   const box=sourceRect(drag.start,drag.current);
   sourceCanvas.append(svgNode('rect',{x:box.x,y:box.y,width:box.w,height:box.h,fill:'#27664c1c',stroke:'#27664c','stroke-width':1.2,'stroke-dasharray':'4 3','vector-effect':'non-scaling-stroke'}));
  }
 }
 function drawPreview(){
  const token=++previewToken,items=selectedCandidates();
  const context=preview.getContext('2d');
  context.clearRect(0,0,preview.width,preview.height);
  if(!items.length)return;
  const layout=previewLayout(items,{width:preview.width,height:preview.height});
  Promise.all(items.map(candidate=>new Promise(resolve=>{
   if(!candidate.preview)return resolve(null);
   const image=new Image();
   image.onload=()=>resolve({candidate,image});image.onerror=()=>resolve(null);image.src=fileURL(project,candidate.preview);
  }))).then(images=>{
   if(token!==previewToken)return;
   context.clearRect(0,0,preview.width,preview.height);
   for(const item of images.filter(Boolean)){
    const place=layout.items.find(entry=>entry.id===item.candidate.id);
    if(place)context.drawImage(item.image,place.x,place.y,place.w,place.h);
   }
  });
 }
 sourceCanvas.addEventListener('pointerdown',event=>{
  if(applying||event.button!==0)return;
  drag={pageId:currentPage().id,start:sourcePoint(event),current:null,client:{x:event.clientX,y:event.clientY}};
  sourceCanvas.setPointerCapture(event.pointerId);
 });
 sourceCanvas.addEventListener('pointermove',event=>{
  if(!drag||applying)return;
  drag.current=sourcePoint(event);
  render();
 });
 sourceCanvas.addEventListener('pointerup',event=>{
  if(!drag||applying)return;
  const active=drag,page=currentPage(),end=sourcePoint(event);
  drag=null;
  const moved=Math.hypot(event.clientX-active.client.x,event.clientY-active.client.y)>4;
  if(moved)addCandidates(candidatesIntersecting(page.candidates||[],sourceRect(active.start,end)));
  else {
   const candidate=candidateAt(end);
   if(candidate)selections=togglePageCandidate(selections,page.id,candidate.id);
  }
  render();
 });
 sourceCanvas.addEventListener('pointercancel',()=>{drag=null;render();});
 function render(){
  const page=currentPage();
  pageList.replaceChildren();
  for(const item of pages){
   const label=item.error?`${item.label} · 无法读取`:item.label;
   const row=button(label,()=>{activePageId=item.id;drag=null;render();},`picker-page${item.id===page.id?' active':''}`);
   row.disabled=Boolean(item.error)||applying;
   pageList.append(row);
   if(item.error)pageList.append(el('p','picker-page-error',item.error));
  }
  const selected=currentSelection();
  sourceStatus.textContent=pickerReady(selected)?`当前页已选 ${selected.size} 项`:'单击内容，或拖动框选多个内容';
  count.textContent=pickerReady(selected)?`当前页已选 ${selected.size} 项`:'请选择当前页面的内容';
  submit.disabled=applying||!pickerReady(selected);submit.textContent=applying?'正在应用…':'确认使用';
  sourceCanvas.style.pointerEvents=applying?'none':'';
  drawSource();
  drawPreview();
 }
 render();
}

export function cleanupDialog(project,apply){
 const asset=project.asset;if(!asset)return;
 const review=new SelectionReview(asset.selected_ids||[],()=>render());
 const suggested=asset.objects.filter(o=>!o.reason).map(o=>o.id);
 const root=dialog('检查与清理 Logo',{canClose:()=>!review.applying});
 const grid=el('div','cleanup-grid'),source=el('div'),clean=el('div');
 source.append(el('p','cleanup-title','原始文件 · 点击对象切换保留'));clean.append(el('p','cleanup-title','当前已应用的干净素材'));
 const sourceBox=el('div','preview-box'),cleanBox=el('div','preview-box');
 const box=asset.source_box||{x:0,y:0,w:asset.width,h:asset.height};
 const svg=svgNode('svg',{viewBox:`${box.x} ${box.y} ${box.w} ${box.h}`});svg.style.touchAction='none';
 svg.append(svgNode('image',{href:fileURL(project,asset.source_preview||asset.source_svg),x:box.x,y:box.y,width:box.w,height:box.h}));sourceBox.append(svg);
 const cleanImage=el('img');cleanImage.src=fileURL(project,project.inputs.logo_preview);cleanImage.alt='已应用的干净 Logo';cleanBox.append(cleanImage);
 source.append(sourceBox);clean.append(cleanBox);grid.append(source,clean);
 root.append(grid,el('div','notice','自动判断仅供参考：底板、标注和轮廓文字可能识别不准。请检查原图；可多选候选合并，或框选需要保留的对象。右侧预览在“应用所选对象”后更新。'));
 const candidates=el('div','candidate-list');root.append(candidates);
 const controls=el('div','asset-actions'),list=el('div','object-list'),count=el('span','muted');
 let rectangleMode=false,start=null,drawn=null;
 const replaceSelection=ids=>review.update(selected=>{selected.clear();for(const id of ids)selected.add(id);});
 controls.append(button('全选',()=>replaceSelection(asset.objects.map(o=>o.id))),button('重置建议',()=>replaceSelection(suggested)),button('清空',()=>replaceSelection([])),button('框选对象',e=>{if(review.applying)return;rectangleMode=!rectangleMode;e.target.classList.toggle('active',rectangleMode);svg.style.cursor=rectangleMode?'crosshair':'';}),count);
 root.append(controls,list);
 const footer=el('div','dialog-footer');
 const applyButton=button('应用所选对象',async()=>{
  if(review.applying||!review.selected.size)return;
  try{await review.apply(apply);closeDialog();}catch(error){dialogError(root,error);}
 },'primary');
 footer.append(button('取消',closeDialog),applyButton);root.append(footer);

 function render(){
  const selected=review.selected;
  count.textContent=review.applying?'正在应用，请稍候…':`保留 ${selected.size} / ${asset.objects.length} 个对象`;
  list.replaceChildren();for(const old of svg.querySelectorAll('[data-object]'))old.remove();
  for(const object of asset.objects){
   const row=el('label','object-row'),check=el('input');check.type='checkbox';check.checked=selected.has(object.id);
   check.onchange=()=>review.update(ids=>{if(check.checked)ids.add(object.id);else ids.delete(object.id);});
   row.append(check,el('span','',object.label||object.id),el('small','',object.reason==='background'?'建议移除 · 底板':object.reason==='dimension'?'建议移除 · 标注':''));list.append(row);
   const b=object.box;if(!b)continue;
   const overlay=svgNode('rect',{x:b.x,y:b.y,width:b.w,height:b.h,fill:selected.has(object.id)?'#3d8b5220':'#b4684510',stroke:selected.has(object.id)?'#478e5b':'#b89a80','stroke-width':1,'vector-effect':'non-scaling-stroke','data-object':object.id});overlay.style.cursor='pointer';
   overlay.addEventListener('click',e=>{if(rectangleMode||review.applying)return;e.stopPropagation();review.update(ids=>{if(ids.has(object.id))ids.delete(object.id);else ids.add(object.id);});});svg.append(overlay);
  }
  candidates.replaceChildren();for(const candidate of asset.candidates||[]){
   const all=candidate.object_ids.every(id=>selected.has(id));
   const b=button('',()=>review.update(ids=>{for(const id of candidate.object_ids)all?ids.delete(id):ids.add(id);}),`candidate${all?' active':''}`);
   if(candidate.preview){const image=el('img');image.src=fileURL(project,candidate.preview);image.alt=candidate.label;b.append(image);}b.append(el('span','',candidate.label));candidates.append(b);
  }
  for(const control of root.querySelectorAll('button,input'))control.disabled=review.applying;
  applyButton.disabled=review.applying||!selected.size;applyButton.textContent=review.applying?'正在应用…':'应用所选对象';
  svg.style.pointerEvents=review.applying?'none':'';root.setAttribute('aria-busy',String(review.applying));
  if(review.applying&&start){start=null;drawn?.remove();drawn=null;}
 }
 const pt=e=>{const point=svg.createSVGPoint();point.x=e.clientX;point.y=e.clientY;return point.matrixTransform(svg.getScreenCTM().inverse());};
 svg.addEventListener('pointerdown',e=>{if(!rectangleMode||review.applying)return;start=pt(e);svg.setPointerCapture(e.pointerId);drawn=svgNode('rect',{fill:'#448b4920',stroke:'#448b49','stroke-width':1,'vector-effect':'non-scaling-stroke'});svg.append(drawn);});
 svg.addEventListener('pointermove',e=>{if(!start||review.applying)return;const end=pt(e),r={x:Math.min(start.x,end.x),y:Math.min(start.y,end.y),width:Math.abs(end.x-start.x),height:Math.abs(end.y-start.y)};for(const [k,v]of Object.entries(r))drawn.setAttribute(k,v);});
 svg.addEventListener('pointerup',e=>{if(!start||review.applying)return;const end=pt(e),r={x:Math.min(start.x,end.x),y:Math.min(start.y,end.y),w:Math.abs(end.x-start.x),h:Math.abs(end.y-start.y)};start=null;drawn.remove();drawn=null;review.update(ids=>{for(const object of asset.objects){const b=object.box;if(b&&b.x<r.x+r.w&&b.x+b.w>r.x&&b.y<r.y+r.h&&b.y+b.h>r.y)ids.add(object.id);}});});
 render();
}
