/**
 * SelectionService — 选中状态管理服务
 *
 * 职责：管理当前选中对象，作为 Single Source of Truth 同步所有面板。
 * 采用观察者模式，订阅者（SceneTree、Viewport、PropertiesPanel）通过回调接收变更通知。
 */

import type { SceneObject } from '../../types/index.ts';

export interface ISelectionService {
  /** 获取当前选中对象 */
  getSelected(): SceneObject | null;

  /** 设置选中对象，通知所有订阅者 */
  setSelected(obj: SceneObject | null): void;

  /** 注册变更监听器，返回取消订阅函数 */
  onChange(callback: (obj: SceneObject | null) => void): () => void;
}

export class SelectionService implements ISelectionService {
  private selected: SceneObject | null = null;
  private listeners: Set<(obj: SceneObject | null) => void> = new Set();

  getSelected(): SceneObject | null {
    return this.selected;
  }

  setSelected(obj: SceneObject | null): void {
    if (this.selected === obj) return; // No change
    this.selected = obj;
    this._notify(obj);
  }

  onChange(callback: (obj: SceneObject | null) => void): () => void {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  private _notify(obj: SceneObject | null): void {
    for (const listener of this.listeners) {
      listener(obj);
    }
  }
}
