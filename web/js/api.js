/**
 * api.js —— 后端 fetch 封装，按错误级别渲染提示条或阻断弹窗（架构文档 3.2）。
 *
 * 统一响应格式：{ok, data, error:{code, message, level, ...}}。
 * - 阻断级（block）：阻断弹窗（含 stderr 原文）
 * - 提示级（warn）：黄色信息条
 */
window.api = (function () {
  'use strict';

  function showToast(message) {
    const bar = document.getElementById('toast-bar');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    bar.appendChild(toast);
    setTimeout(function () {
      toast.remove();
    }, 6000);
  }

  function showBlock(code, message, stderr) {
    const root = document.getElementById('modal-root');
    root.innerHTML = '';
    root.className = 'open';

    const modal = document.createElement('div');
    modal.className = 'modal';

    const head = document.createElement('div');
    head.className = 'modal-head';
    head.textContent = '操作失败';

    const body = document.createElement('div');
    body.className = 'modal-body';
    const msg = document.createElement('div');
    msg.textContent = message;
    body.appendChild(msg);
    if (stderr) {
      const pre = document.createElement('pre');
      pre.className = 'modal-stderr';
      pre.textContent = stderr;
      body.appendChild(pre);
    }

    const foot = document.createElement('div');
    foot.className = 'modal-foot';
    const close = document.createElement('button');
    close.className = 'btn btn-primary';
    close.textContent = '知道了';
    close.addEventListener('click', function () {
      root.className = '';
      root.innerHTML = '';
    });
    foot.appendChild(close);

    modal.appendChild(head);
    modal.appendChild(body);
    modal.appendChild(foot);
    root.appendChild(modal);
  }

  async function request(path, options) {
    let resp;
    try {
      resp = await fetch(path, options);
    } catch (err) {
      showBlock('NETWORK_ERROR', '无法连接本地服务：' + err.message);
      throw err;
    }

    let json;
    try {
      json = await resp.json();
    } catch (err) {
      showBlock('BAD_RESPONSE', '服务返回了无法解析的内容');
      throw err;
    }

    if (json && json.ok) {
      return json.data;
    }

    const err = (json && json.error) || { code: 'UNKNOWN', message: '未知错误', level: 'block' };
    if (err.level === 'warn') {
      showToast(err.message);
    } else {
      showBlock(err.code, err.message, err.stderr);
    }
    throw new Error(err.message || '请求失败');
  }

  function get(path) {
    return request(path);
  }

  function post(path, body) {
    return request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  function put(path, body) {
    return request(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  function upload(path, file) {
    const fd = new FormData();
    fd.append('file', file);
    return request(path, { method: 'POST', body: fd });
  }

  function bagFileUrl(projectName, relPath) {
    // 分段编码：保留路径中的斜杠，仅编码各段（含中文文件名）
    const parts = String(relPath).split('/').map(encodeURIComponent).join('/');
    return '/api/projects/' + encodeURIComponent(projectName) + '/file/' + parts;
  }

  // 通用项目内文件 URL（包图 / logo.svg 等），与 bagFileUrl 同逻辑
  function fileUrl(projectName, relPath) {
    return bagFileUrl(projectName, relPath);
  }

  function saveProject(proj) {
    // 保存项目（原子写入），失败仅提示不阻断交互
    return put('/api/projects/' + encodeURIComponent(proj.name), proj)
      .catch(function () {
        /* 保存失败已在 request 内弹窗提示 */
      });
  }

  return {
    get: get,
    post: post,
    put: put,
    upload: upload,
    bagFileUrl: bagFileUrl,
    fileUrl: fileUrl,
    saveProject: saveProject,
    showToast: showToast,
    showBlock: showBlock,
  };
})();
