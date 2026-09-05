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
 let selected=new Set(asset.selected_candidate_ids||[]);
 let applying=false;
 let previewToken=0;
 const root=dialog('选择 Logo 内容',{canClose:()=>!applying});
 const grid=el('div','logo-picker-grid');
 const pagesColumn=el('section','picker-pages');
 const candidatesColumn=el('section','picker-candidates');
 const previewColumn=el('section','picker-preview');
 const pageList=el('div','picker-page-list');
 const candidateList=el('div','picker-candidate-list');
 const count=el('p','muted');
 const preview=el('canvas','picker-preview-canvas');
 preview.width=480;
 preview.height=250;
 pagesColumn.append(el('h3','','页面'),pageList);
 candidatesColumn.append(el('h3','','候选内容'),candidateList);
 previewColumn.append(el('h3','','已选预览'),count,preview);
 grid.append(pagesColumn,candidatesColumn,previewColumn);
 root.append(grid);
 const footer=el('div','dialog-footer');
 const submit=button('确认使用',async()=>{
  if(applying||!pickerReady(selected))return;
  applying=true;render();
  try{await applyCandidateIds([...selected]);closeDialog();}catch(error){dialogError(root,error);}finally{applying=false;render();}
 },'primary');
 footer.append(button('取消',closeDialog),submit);root.append(footer);

 function currentPage(){return pages.find(page=>page.id===activePageId)||first;}
 function selectedCandidates(){return pages.flatMap(page=>page.candidates||[]).filter(candidate=>selected.has(candidate.id));}
 function drawPreview(){
  const token=++previewToken,items=selectedCandidates();
  const context=preview.getContext('2d');
  context.clearRect(0,0,preview.width,preview.height);
  if(!items.length)return;
  Promise.all(items.map(candidate=>new Promise(resolve=>{
   if(!candidate.preview)return resolve(null);
   const image=new Image();
   image.onload=()=>resolve(image);image.onerror=()=>resolve(null);image.src=fileURL(project,candidate.preview);
  }))).then(images=>{
   if(token!==previewToken)return;
   context.clearRect(0,0,preview.width,preview.height);
   const loaded=images.filter(Boolean);
   if(!loaded.length)return;
   const slotWidth=preview.width/loaded.length;
   for(const [index,image]of loaded.entries()){
    const scale=Math.min((slotWidth-24)/image.naturalWidth,(preview.height-24)/image.naturalHeight);
    const width=image.naturalWidth*scale,height=image.naturalHeight*scale;
    context.drawImage(image,index*slotWidth+(slotWidth-width)/2,(preview.height-height)/2,width,height);
   }
  });
 }
 function render(){
  const page=currentPage();
  pageList.replaceChildren();
  for(const item of pages){
   const label=item.error?`${item.label} · 无法读取`:item.label;
   const row=button(label,()=>{activePageId=item.id;render();},`picker-page${item.id===page.id?' active':''}`);
   row.disabled=Boolean(item.error)||applying;
   pageList.append(row);
   if(item.error)pageList.append(el('p','picker-page-error',item.error));
  }
  candidateList.replaceChildren();
  for(const candidate of page.candidates||[]){
   const row=el('label',`picker-candidate${selected.has(candidate.id)?' selected':''}`),check=el('input');
   check.type='checkbox';check.checked=selected.has(candidate.id);check.disabled=applying;
   check.onchange=()=>{selected=mergeCandidateIds(selected,candidate.id);render();};
   row.append(check);
   if(candidate.preview){const image=el('img');image.src=fileURL(project,candidate.preview);image.alt='候选内容预览';row.append(image);}
   row.append(el('span','',candidate.label));candidateList.append(row);
  }
  if(!(page.candidates||[]).length)candidateList.append(el('p','empty-note','此页没有可用的候选内容。'));
  count.textContent=pickerReady(selected)?`已选 ${selected.size} 项`:'请选择至少一项';
  submit.disabled=applying||!pickerReady(selected);submit.textContent=applying?'正在应用…':'确认使用';
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
