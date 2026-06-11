/**
 * SceneService — 场景管理服务
 *
 * 职责：解析 USDA 内容、构建场景对象树、提供对象查询接口。
 * 不依赖任何 DOM 或 Three.js API。
 */

import type { SceneObject, PikiInstance, PikiCollection } from '../../types/index.ts';
import type { IUsdaParser } from '../../infrastructure/parsers/UsdaParser.ts';
import { inferTypeFromId, typeColor } from '../../utils/index.ts';

export interface ISceneService {
  /** 从 USDA 文本加载场景 */
  loadFromUsda(content: string): void;

  /** 从实例数据生成占位场景 */
  loadFromInstances(collections: PikiCollection[]): void;

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

  /**
   * 从 YAML 实例数据生成真实物理布局的 3D 场景。
   *
   * 布局规则：
   * - 机柜（rack）按 rack_id 分组，排成一排
   * - 设备（device）安装在所属机柜内部，按 position_u 从下往上排列
   * - PDU 挂在机柜背面/侧面
   * - 无 rack_id 的实例平铺排列
   */
  loadFromInstances(collections: PikiCollection[]): void {
    // Flatten all instances
    const allInstances: PikiInstance[] = [];
    for (const col of collections) {
      allInstances.push(...col.instances);
    }

    // Group by rack_id
    const rackMap = new Map<string, PikiInstance[]>(); // rack_id -> rack instance + its devices/pdus
    const orphanInstances: PikiInstance[] = []; // no rack_id

    for (const inst of allInstances) {
      const rackId = inst.raw.rack_id as string | undefined;
      if (rackId) {
        if (!rackMap.has(rackId)) rackMap.set(rackId, []);
        rackMap.get(rackId)!.push(inst);
      } else {
        orphanInstances.push(inst);
      }
    }

    const objects: SceneObject[] = [];
    const rackSpacing = 3.0; // 机柜之间的间距

    // Identify rack instances (the container itself)
    const rackIds = Array.from(rackMap.keys());
    const totalRackWidth = rackIds.length * 0.6 + (rackIds.length - 1) * rackSpacing;
    let rackOffsetX = -totalRackWidth / 2;

    for (const rackId of rackIds) {
      const members = rackMap.get(rackId)!;
      const rackInst = members.find((i) => i.id === rackId);
      const devices = members.filter((i) => inferTypeFromId(i.id) === 'device');
      const pdus = members.filter((i) => inferTypeFromId(i.id) === 'pdu');

      // Rack dimensions
      const rackW = 0.6;
      const rackH = 1.8;
      const rackD = 1.0;
      const rackX = rackOffsetX + rackW / 2;
      const rackZ = 0;

      // Create rack scene object
      const rackObj: SceneObject = {
        name: rackId,
        displayName: (rackInst?.raw.name as string) || null,
        type: 'rack',
        depth: 0,
        parent: null,
        children: [],
        geometry: {
          type: 'cube',
          transform: [
            rackW, 0, 0, 0,
            0, rackH, 0, 0,
            0, 0, rackD, 0,
            rackX, rackH / 2, rackZ, 1,
          ],
          color: hexToRgb(typeColor('rack')),
          size: 1,
        },
      };
      objects.push(rackObj);

      // Devices inside rack, sorted by position_u (bottom to top)
      const sortedDevices = devices
        .map((d) => ({ inst: d, u: Number(d.raw.position_u) || 0 }))
        .sort((a, b) => a.u - b.u);

      for (const { inst, u } of sortedDevices) {
        const devW = 0.45;
        const devH = 0.09; // ~1U height
        const devD = 0.75;

        // Position: centered in rack width, at U position from bottom
        const uHeight = rackH / 42; // 1U = total_height / 42U
        const devY = u * uHeight + devH / 2;
        const devX = rackX;
        const devZ = rackZ;

        const devObj: SceneObject = {
          name: inst.id,
          displayName: (inst.raw.name as string) || null,
          type: 'device',
          depth: 1,
          parent: rackObj,
          children: [],
          geometry: {
            type: 'cube',
            transform: [
              devW, 0, 0, 0,
              0, devH, 0, 0,
              0, 0, devD, 0,
              devX, devY, devZ, 1,
            ],
            color: hexToRgb(typeColor('device')),
            size: 1,
          },
        };
        rackObj.children.push(devObj);
        objects.push(devObj);
      }

      // PDUs: mounted on the back of the rack
      for (let pi = 0; pi < pdus.length; pi++) {
        const pdu = pdus[pi];
        const pduW = 0.08;
        const pduH = 1.2;
        const pduD = 0.08;

        // Left and right side of rack back
        const pduX = rackX + (pi === 0 ? -rackW / 2 - pduW / 2 - 0.02 : rackW / 2 + pduW / 2 + 0.02);
        const pduY = rackH / 2;
        const pduZ = rackZ - rackD / 2 - pduD / 2 - 0.02;

        const pduObj: SceneObject = {
          name: pdu.id,
          displayName: (pdu.raw.name as string) || null,
          type: 'pdu',
          depth: 1,
          parent: rackObj,
          children: [],
          geometry: {
            type: 'cube',
            transform: [
              pduW, 0, 0, 0,
              0, pduH, 0, 0,
              0, 0, pduD, 0,
              pduX, pduY, pduZ, 1,
            ],
            color: hexToRgb(typeColor('pdu')),
            size: 1,
          },
        };
        rackObj.children.push(pduObj);
        objects.push(pduObj);
      }

      rackOffsetX += rackW + rackSpacing;
    }

    // Orphan instances (no rack_id): lay out in a flat grid
    if (orphanInstances.length > 0) {
      const itemsPerRow = 4;
      const itemSpacing = 1.5;
      const cols = Math.min(orphanInstances.length, itemsPerRow);
      const rows = Math.ceil(orphanInstances.length / itemsPerRow);
      const gridW = (cols - 1) * itemSpacing;
      const gridD = (rows - 1) * itemSpacing;
      const orphanOffsetX = -gridW / 2;
      const orphanOffsetZ = rackIds.length > 0 ? 4 : 0; // behind racks if racks exist

      for (let i = 0; i < orphanInstances.length; i++) {
        const inst = orphanInstances[i];
        const row = Math.floor(i / itemsPerRow);
        const col = i % itemsPerRow;
        const type = inferTypeFromId(inst.id);

        let sx = 0.8, sy = 0.8, sz = 0.8;
        if (type === 'rack') { sx = 0.6; sy = 1.8; sz = 1.0; }
        else if (type === 'device') { sx = 0.45; sy = 0.09; sz = 0.75; }
        else if (type === 'pdu') { sx = 0.12; sy = 0.6; sz = 0.12; }

        const x = orphanOffsetX + col * itemSpacing;
        const z = orphanOffsetZ + row * itemSpacing - gridD / 2;
        const y = sy / 2;

        const obj: SceneObject = {
          name: inst.id,
          displayName: (inst.raw.name as string) || null,
          type,
          depth: 0,
          parent: null,
          children: [],
          geometry: {
            type: 'cube',
            transform: [
              sx, 0, 0, 0,
              0, sy, 0, 0,
              0, 0, sz, 0,
              x, y, z, 1,
            ],
            color: hexToRgb(typeColor(type)),
            size: 1,
          },
        };
        objects.push(obj);
      }
    }

    this.objects = objects;
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

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return { r: 0.7, g: 0.7, b: 0.7 };
  return {
    r: parseInt(result[1], 16) / 255,
    g: parseInt(result[2], 16) / 255,
    b: parseInt(result[3], 16) / 255,
  };
}
