export const $ = id=>document.getElementById(id);
export function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;}
export function button(text,action,cls=''){const node=el('button',cls,text);node.type='button';node.addEventListener('click',action);return node;}
export function field(label,value,onChange,{type='number',min,step='0.01'}={}){const wrap=el('label','field',label),input=el('input');input.type=type;input.value=value??'';if(type==='number'){input.step=step;if(min!==undefined)input.min=min;}input.addEventListener('change',()=>onChange(type==='number'?Number(input.value):input.value));wrap.append(input);return wrap;}
export function section(title){const node=el('section','properties-section');node.append(el('h3','',title));return node;}
let canCloseDialog=()=>true;
export function dialog(title,{canClose=()=>true}={}){canCloseDialog=canClose;const root=$('dialog-content');root.replaceChildren();const head=el('div','dialog-header');head.append(el('h2','',title),button('×',()=>closeDialog()));root.append(head);$('dialog').oncancel=e=>{if(!canCloseDialog())e.preventDefault();};if(!$('dialog').open)$('dialog').showModal();return root;}
export function closeDialog(){if(!canCloseDialog())return false;$('dialog').close();return true;}
export function dialogError(root,error){let node=root.querySelector('.dialog-error');if(!node){node=el('div','dialog-error');node.setAttribute('role','alert');root.append(node);}node.textContent=error.message||String(error);}
export function errorBanner(error){$('error-message').textContent=error.message||String(error);$('error-banner').hidden=false;}
