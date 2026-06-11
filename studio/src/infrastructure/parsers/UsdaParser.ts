/**
 * UsdaParser — USDA 文本解析器
 *
 * 职责：将 USDA（Universal Scene Description ASCII）文本解析为 SceneObject 树。
 * 当前为自研轻量实现，仅解析渲染代理几何所需的结构（Xform、Cube、transform、displayColor）。
 * 未来如需完整 USD 支持（引用、材质、动画），可替换为 USD WASM。
 */

import type { SceneObject, GeometryInfo } from '../../types/index.ts';

export interface IUsdaParser {
  parse(content: string): SceneObject[];
}

export class SimpleUsdaParser implements IUsdaParser {
  parse(content: string): SceneObject[] {
    const objects: SceneObject[] = [];
    const lines = content.split('\n');
    const stack: SceneObject[] = [];
    let currentObj: SceneObject | null = null;
    let currentGeo: GeometryInfo | null = null;
    let braceDepth = 0;

    for (const line of lines) {
      const trimmed = line.trim();
      const openBraces = (line.match(/\{/g) || []).length;
      const closeBraces = (line.match(/\}/g) || []).length;

      // def Xform "name" (displayName = "...")
      const xformMatch = trimmed.match(/def\s+Xform\s+"([^"]+)"\s*(?:\(([^)]*)\))?/);
      if (xformMatch) {
        const obj: SceneObject = {
          name: xformMatch[1],
          displayName: null,
          type: 'group',
          depth: braceDepth,
          parent: stack.length > 0 ? stack[stack.length - 1] : null,
          geometry: null,
          children: [],
        };

        if (xformMatch[2]) {
          const dnMatch = xformMatch[2].match(/displayName\s*=\s*"([^"]*)"/);
          if (dnMatch) obj.displayName = dnMatch[1];
        }

        // Heuristic type detection based on naming conventions
        if (obj.name.startsWith('RACK')) obj.type = 'rack';
        else if (obj.name.startsWith('SRV') || obj.name.startsWith('device')) obj.type = 'device';
        else if (obj.name.startsWith('PDU')) obj.type = 'pdu';
        else if (['devices', 'racks', 'pdus'].includes(obj.name)) obj.type = 'collection';

        if (stack.length > 0) {
          stack[stack.length - 1].children.push(obj);
        }

        objects.push(obj);
        currentObj = obj;
        stack.push(obj);
      }

      // def Cube "geometry" or def Mesh "geometry"
      const cubeMatch = trimmed.match(/def\s+(Cube|Mesh)\s+"geometry"/);
      if (cubeMatch && currentObj) {
        currentGeo = {
          type: cubeMatch[1].toLowerCase(),
          transform: [
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1,
          ],
          color: { r: 0.7, g: 0.7, b: 0.7 },
          size: 1,
        };
        currentObj.geometry = currentGeo;
      }

      // matrix4d xformOp:transform = (...)
      const matrixMatch = trimmed.match(/matrix4d\s+xformOp:transform\s*=\s*(\([^)]+\))/);
      if (matrixMatch && currentGeo) {
        const nums = matrixMatch[1].match(/-?\d+\.?\d*(?:e[+-]?\d+)?/gi)?.map(Number);
        if (nums && nums.length === 16) {
          currentGeo.transform = nums;
        }
      }

      // color3f[] primvars:displayColor = [(...)]
      const colorMatch = trimmed.match(/color3f\[\]\s+primvars:displayColor\s*=\s*\[(\([^)]+\))\]/);
      if (colorMatch && currentGeo) {
        const nums = colorMatch[1].match(/\d+\.?\d*/g)?.map(Number);
        if (nums && nums.length >= 3) {
          currentGeo.color = { r: nums[0], g: nums[1], b: nums[2] };
        }
      }

      // double size = N
      const sizeMatch = trimmed.match(/double\s+size\s*=\s*(\d+\.?\d*)/);
      if (sizeMatch && currentGeo) {
        currentGeo.size = parseFloat(sizeMatch[1]);
      }

      braceDepth += openBraces - closeBraces;

      if (closeBraces > 0 && stack.length > 0) {
        for (let b = 0; b < closeBraces && stack.length > 0; b++) {
          stack.pop();
        }
        currentObj = stack.length > 0 ? stack[stack.length - 1] : null;
        currentGeo = null;
      }
    }

    return objects;
  }
}
