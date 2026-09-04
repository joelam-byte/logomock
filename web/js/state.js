/**
 * state.js —— 单一数据源（架构文档 3.2）。
 *
 * 框坐标、px_per_mm、方案数值只存此处。任何模块不得自行缓存业务数据。
 * 不得触碰 DOM 与 Canvas API。
 *
 * 提供 get / set / update / subscribe，变更时广播给订阅者。
 */
window.state = (function () {
  'use strict';

  const data = {
    currentStep: '1',
    projectName: '',
    project: null,        // 完整 project 数据（inputs/calibration/frames/schemes）
    bagImageReady: false, // 包图是否已加载进 Canvas（渲染资源状态）
    logoReady: false,     // logo.svg 是否已加载进 Canvas（渲染资源状态）
    currentSchemeId: null,
    exportedSchemeIds: [], // 已导出方案 id（步骤4 导出成功后标记，供方案条绿勾）
  };

  const listeners = new Set();

  function get(key) {
    if (key === undefined) return data;
    return data[key];
  }

  function set(key, value) {
    data[key] = value;
    emit();
  }

  function update(partial) {
    Object.assign(data, partial);
    emit();
  }

  function subscribe(fn) {
    listeners.add(fn);
    return function unsubscribe() {
      listeners.delete(fn);
    };
  }

  function emit() {
    listeners.forEach(function (fn) {
      fn(data);
    });
  }

  return { get: get, set: set, update: update, subscribe: subscribe, emit: emit };
})();
