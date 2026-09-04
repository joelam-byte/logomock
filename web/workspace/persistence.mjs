export class SaveQueue {
 constructor(save,onSaved=()=>{},onError=()=>{},delay=650){Object.assign(this,{save,onSaved,onError,delay,pending:null,running:null,error:null,revision:null,timer:null});}
 schedule(value){this.pending=structuredClone(value);clearTimeout(this.timer);if(!this.error)this.timer=setTimeout(()=>this.flush().catch(()=>{}),this.delay);}
 async flush(){clearTimeout(this.timer);if(this.error)throw this.error;if(this.running)return this.running;if(!this.pending)return;
  this.running=(async()=>{while(this.pending){const data=this.pending;this.pending=null;if(this.revision!==null)data.revision=this.revision;try{const saved=await this.save(data);this.revision=saved.revision;this.onSaved(saved);}catch(error){if(!this.pending)this.pending=data;this.error=error;this.onError(error);throw error;}}})();
  try{await this.running;}finally{clearTimeout(this.timer);this.running=null;}
 }
 retry(){if(this.error?.code==='REVISION_CONFLICT')return Promise.reject(this.error);this.error=null;return this.flush();}
}
export async function api(path,{method='GET',body}={}) {const options={method};if(body instanceof FormData)options.body=body;else if(body!==undefined){options.body=JSON.stringify(body);options.headers={'Content-Type':'application/json'};}let response;try{response=await fetch(path,options);}catch{throw new Error('无法连接本地服务，请确认 LogoMock 正在运行。');}let result;try{result=await response.json();}catch{throw new Error(`服务返回无效响应 (${response.status})`);}if(!response.ok||!result.ok)throw Object.assign(new Error(result.error?.message||`请求失败 (${response.status})`),{code:result.error?.code});return result.data;}
export const projectURL = name => `/api/projects/${encodeURIComponent(name)}`;
export async function runExclusive(state,work,onBusyChange=()=>{}){
 if(state.busy)throw Object.assign(new Error('当前操作尚未完成，请稍后再试。'),{code:'OPERATION_BUSY'});
 state.busy=true;
 try{onBusyChange(true);return await work();}finally{state.busy=false;onBusyChange(false);}
}
export const fileURL = (p,path) => path ? `${projectURL(p.name)}/file/${path.split('/').map(encodeURIComponent).join('/')}` : '';
