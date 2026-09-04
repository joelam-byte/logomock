export const copy = value => structuredClone(value);
export const positive = n => Number.isFinite(n) && n > 0;
export const validRect = r => r && Number.isFinite(r.x) && Number.isFinite(r.y) && positive(r.w) && positive(r.h);
export const ppmOf = p => validRect(p?.calibration?.product_frame) && positive(p.calibration.width_mm) ? p.calibration.product_frame.w / p.calibration.width_mm : 0;
export function projectRect(s,f,ppm) {return {x:f.x+s.offset_mm.left*ppm,y:f.y+f.h-(s.offset_mm.bottom+s.size_mm.h)*ppm,w:s.size_mm.w*ppm,h:s.size_mm.h*ppm};}
export function canonicalScheme(s,f,ppm) {const r=s.logo_px;return {...s,size_mm:{w:r.w/ppm,h:r.h/ppm},offset_mm:{left:(r.x-f.x)/ppm,bottom:(f.y+f.h-r.y-r.h)/ppm}};}
export function resizeAspect(r,w,h,aspect) {const width=Math.max(0.1,w);return {...r,w:width,h:width/aspect};}
export function newScheme(p,frameId,id=crypto.randomUUID()) {
 const ppm=ppmOf(p),f=p.frames.find(f=>f.id===frameId);if(!ppm||!validRect(f))return null;
 const aspect=p.asset?.width/p.asset?.height || 2,w=Math.min(50,f.w/ppm*.5),h=w/aspect;
 const s={id,name:`方案 ${(p.schemes?.length||0)+1}`,frame_id:f.id,size_mm:{w,h},offset_mm:{left:(f.w/ppm-w)/2,bottom:(f.h/ppm-h)/2},color:null};return {...s,logo_px:projectRect(s,f,ppm)};
}
export function reproject(p) {const q=copy(p),ppm=ppmOf(q);if(!ppm)return q;q.schemes=(q.schemes||[]).map(s=>{const f=q.frames.find(f=>f.id===s.frame_id);if(!validRect(f))return s;const canonical=s.size_mm&&s.offset_mm?s:canonicalScheme(s,f,ppm);return {...canonical,logo_px:projectRect(canonical,f,ppm)};});return q;}
export function exportReady(p) {const ppm=ppmOf(p);return Boolean(ppm&&p.asset?.selected_ids?.length&&p.inputs?.logo_preview&&p.schemes?.length&&p.schemes.every(s=>positive(s.size_mm?.w)&&positive(s.size_mm?.h)&&Number.isFinite(s.offset_mm?.left)&&Number.isFinite(s.offset_mm?.bottom)&&validRect(p.frames.find(f=>f.id===s.frame_id))&&validRect(s.logo_px)));}
export class History {
 constructor(initial){this.entries=[copy(initial)];this.index=0;}
 get canUndo(){return this.index>0;} get canRedo(){return this.index<this.entries.length-1;}
 commit(value){if(JSON.stringify(value)===JSON.stringify(this.entries[this.index]))return;this.entries.splice(this.index+1);this.entries.push(copy(value));if(this.entries.length>80)this.entries.shift();this.index=this.entries.length-1;}
 undo(){if(this.canUndo)this.index--;return copy(this.entries[this.index]);} redo(){if(this.canRedo)this.index++;return copy(this.entries[this.index]);}
}
