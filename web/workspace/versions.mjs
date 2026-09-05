import {button,el} from './ui.mjs';

export function formatVersionLabel(version) {
 return version.read_only?'旧版导出':`第 ${version.number} 版`;
}

export function versionActionState(version) {
 return {canRestore:true,canDelete:!version.read_only};
}

export function formatVersionTime(value) {
 const date=new Date(value);
 return Number.isNaN(date.getTime())?'时间未知':date.toLocaleString('zh-CN',{year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
}

export function renderVersionList(root,versions,selectedId,onSelect) {
 root.replaceChildren();
 if(!versions.length){root.append(el('p','empty-note','暂无版本'));return;}
 for(const version of versions){
  const row=button('',()=>onSelect(version.version_id),`version-row${version.version_id===selectedId?' active':''}`);
  row.append(el('strong','',formatVersionLabel(version)),el('small','',formatVersionTime(version.created_at)));
  root.append(row);
 }
}
