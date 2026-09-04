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
