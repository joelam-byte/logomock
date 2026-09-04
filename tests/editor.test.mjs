import test from 'node:test';
import assert from 'node:assert/strict';
import { projectRect, canonicalScheme, resizeAspect, newScheme, reproject, exportReady, History } from '../web/workspace/geometry.mjs';
import { SaveQueue, runExclusive } from '../web/workspace/persistence.mjs';
import { SelectionReview } from '../web/workspace/assets.mjs';
import { Editor } from '../web/workspace/editor.mjs';

const fixture = () => ({name:'测试',revision:3,calibration:{product_frame:{x:10,y:10,w:600,h:800},width_mm:300},frames:[{id:'f',x:30,y:40,w:400,h:600}],schemes:[],asset:{width:200,height:100,selected_ids:['a']},inputs:{logo_preview:'clean.png'}});
test('millimetres determine bottom anchored placement without rounding',()=>{
 assert.deepEqual(projectRect({size_mm:{w:40,h:20},offset_mm:{left:15,bottom:25}}, {x:30,y:40,w:400,h:600},2),{x:60,y:550,w:80,h:40});
 const s=canonicalScheme({logo_px:{x:60.5,y:549,w:80,h:40}},fixture().frames[0],2);
 assert.equal(s.offset_mm.left,15.25); assert.equal(s.offset_mm.bottom,25.5);
});
test('aspect resize stays positive and a new scheme is centered with physical size',()=>{
 assert.deepEqual(resizeAspect({x:0,y:0,w:100,h:50},160,80,2),{x:0,y:0,w:160,h:80});
 const s=newScheme(fixture(),'f','s'); assert.deepEqual(s.size_mm,{w:50,h:25}); assert.deepEqual(s.logo_px,{x:180,y:315,w:100,h:50});
 assert.equal(newScheme({...fixture(),calibration:{width_mm:0}},'f','bad'),null);
});
test('calibration edits preserve physical size and offset',()=>{
 const p=fixture(); p.schemes=[{id:'s',frame_id:'f',size_mm:{w:40,h:20},offset_mm:{left:15,bottom:25}}]; p.calibration.width_mm=150;
 const q=reproject(p); assert.deepEqual(q.schemes[0].logo_px,{x:90,y:460,w:160,h:80}); assert.equal(q.schemes[0].size_mm.w,40);
});
test('history commits a whole gesture once and clears redo on a new edit',()=>{
 const h=new History({x:0});h.commit({x:50}); assert.deepEqual(h.undo(),{x:0}); assert.deepEqual(h.redo(),{x:50});h.undo();h.commit({x:20});assert.equal(h.canRedo,false);
});
test('export rejects legacy assets and invalid or zero sized geometry',()=>{
 const p=fixture();p.schemes=[newScheme(p,'f','s')];assert.equal(exportReady(p),true);p.asset=null;assert.equal(exportReady(p),false);p.asset={selected_ids:['a']};p.schemes[0].size_mm.w=0;assert.equal(exportReady(p),false);
});
test('serialized saves use latest returned revision without overwriting later edits',async()=>{
 let release;const sent=[];let local={revision:3,x:1};const queue=new SaveQueue(async data=>{sent.push(structuredClone(data)); if(sent.length===1)await new Promise(r=>release=r);return {...data,revision:data.revision+1};}, data=>{local.revision=data.revision;},()=>{},100000);
 queue.schedule(local);const flush=queue.flush();await Promise.resolve();local.x=9;queue.schedule(local);release();await flush;assert.deepEqual(sent,[{revision:3,x:1},{revision:4,x:9}]);assert.deepEqual(local,{revision:5,x:9});
});
test('revision conflicts stop queued writes and remain visible to flush',async()=>{
 let calls=0;const error=Object.assign(new Error('conflict'),{code:'REVISION_CONFLICT'});const q=new SaveQueue(async()=>{calls++;throw error;},()=>{},()=>{},100000);q.schedule({revision:1});await assert.rejects(q.flush(),{code:'REVISION_CONFLICT'});q.schedule({revision:1,x:2});await assert.rejects(q.flush(),{code:'REVISION_CONFLICT'});assert.equal(calls,1);
});
test('cleanup application freezes selection and rejects reapply until the request resolves',async()=>{
 let release;const sent=[];const review=new SelectionReview(['logo']);
 const pending=review.apply(async ids=>{sent.push(ids);await new Promise(resolve=>release=resolve);return 'applied';});
 assert.equal(review.applying,true);
 review.update(ids=>ids.add('dimension'));
 assert.deepEqual([...review.selected],['logo']);
 await assert.rejects(review.apply(async ids=>sent.push(ids)),{code:'OPERATION_BUSY'});
 assert.deepEqual(sent,[['logo']]);
 release();assert.equal(await pending,'applied');assert.equal(review.applying,false);
 review.update(ids=>ids.add('second'));assert.deepEqual([...review.selected],['logo','second']);
});
test('failed cleanup unlocks the unchanged selection for an explicit retry',async()=>{
 const review=new SelectionReview(['logo']);await assert.rejects(review.apply(async()=>{throw new Error('request failed');}),/request failed/);
 assert.equal(review.applying,false);assert.deepEqual([...review.selected],['logo']);
 assert.deepEqual(await review.apply(async ids=>ids),['logo']);
});
test('busy workspace rejects a concurrent mutation instead of reporting a skipped success',async()=>{
 const state={busy:false};let release;const pending=runExclusive(state,()=>new Promise(resolve=>release=resolve));
 await assert.rejects(runExclusive(state,async()=> 'unexpected success'),{code:'OPERATION_BUSY'});
 assert.equal(state.busy,true);release('first result');assert.equal(await pending,'first result');assert.equal(state.busy,false);
 assert.equal(await runExclusive(state,async()=> 'next result'),'next result');
});
test('image load notifies thumbnail rendering after the current image dimensions change',()=>{
 const OriginalImage=globalThis.Image,images=[],sizes=[];
 globalThis.Image=class {constructor(){images.push(this);}};
 try{
  const editor=Object.assign(Object.create(Editor.prototype),{imagePath:'',imageSize:{w:800,h:900},fit(){},onImageLoad(){sizes.push({...this.imageSize});}});
  editor.loadImage({name:'project',inputs:{bag_image:'first.png'}});
  editor.loadImage({name:'project',inputs:{bag_image:'second.png'}});
  images[0].naturalWidth=400;images[0].naturalHeight=800;images[0].onload();
  assert.deepEqual(sizes,[]);
  images[1].naturalWidth=1600;images[1].naturalHeight=600;images[1].onload();
  assert.deepEqual(sizes,[{w:1600,h:600}]);
 }finally{globalThis.Image=OriginalImage;}
});
