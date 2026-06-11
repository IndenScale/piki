/**
 * SceneService — 场景管理服务
 *
 * 职责：解析 USDA 内容、构建场景对象树、提供对象查询接口。
 * 不依赖任何 DOM 或 Three.js API。
 */

import type { SceneObject } from '../../types/index.ts';
import type { IUsdaParser } from '../../infrastructure/parsers/UsdaParser.ts';

export interface ISceneService {
  /** 从 USDA 文本加载场景 */
  loadFromUsda(content: string): void;

  /** 获取所有场景对象（扁平列表） */
  getAllObjects(): SceneObject[];

  /** 按名称查找场景对象 */
  getObjectByName(name: string): SceneObject | null;

  /** 按类型过滤场景对象 */
  getObjectsByType(type: SceneObject['type']): SceneObject[];
}

export class SceneService implements ISceneService {
  private parser: IUsdaParser;
  private objects: SceneObject[] = [];
  private objectMap: Map<string, SceneObject> = new Map();

  constructor(parser: IUsdaParser) {
    this.parser = parser;
  }

  loadFromUsda(content: string): void {
    this.objects = this.parser.parse(content);
    this.objectMap.clear();
    this._indexObjects(this.objects);
  }

  getAllObjects(): SceneObject[] {
    return this.objects;
  }

  getObjectByName(name: string): SceneObject | null {
    return this.objectMap.get(name) || null;
  }

  getObjectsByType(type: SceneObject['type']): SceneObject[] {
    return this.objects.filter((obj) => obj.type === type);
  }

  private _indexObjects(objects: SceneObject[]): void {
    for (const obj of objects) {
      this.objectMap.set(obj.name, obj);
      if (obj.children.length > 0) {
        this._indexObjects(obj.children);
      }
    }
  }
}
