/**
 * YamlParser — YAML 文本解析器
 *
 * 职责：将 YAML 文本解析为 JavaScript 对象。
 * 当前为自研轻量实现，仅支持 piki 实例文件常用的简单结构。
 * 未来如需完整 YAML 支持（锚点、标签、多文档），可替换为 yaml 库。
 */

export interface IYamlParser {
  parse(text: string): Record<string, unknown>;
}

export class SimpleYamlParser implements IYamlParser {
  parse(text: string): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    const lines = text.split('\n');
    const indentStack: { key: string; indent: number }[] = [];

    for (const line of lines) {
      if (!line.trim() || line.trim().startsWith('#')) continue;

      const match = line.match(/^(\s*)(\w+):\s*(.*)$/);
      if (!match) continue;

      const indent = match[1].length;
      const key = match[2];
      const value = match[3].trim();

      // Pop stack until we find the right parent
      while (indentStack.length > 0 && indentStack[indentStack.length - 1].indent >= indent) {
        indentStack.pop();
      }

      if (indentStack.length === 0) {
        if (value) {
          result[key] = this._parseValue(value);
        } else {
          result[key] = {};
        }
        indentStack.push({ key, indent });
      } else {
        let target: Record<string, unknown> = result;
        for (const entry of indentStack) {
          const v = target[entry.key];
          if (v && typeof v === 'object' && !Array.isArray(v)) {
            target = v as Record<string, unknown>;
          }
        }
        if (value) {
          target[key] = this._parseValue(value);
        } else {
          target[key] = {};
        }
        indentStack.push({ key, indent });
      }
    }

    return result;
  }

  private _parseValue(value: string): unknown {
    if (value === 'true') return true;
    if (value === 'false') return false;
    if (value === 'null' || value === '~') return null;
    if (/^-?\d+$/.test(value)) return parseInt(value, 10);
    if (/^-?\d+\.\d+$/.test(value)) return parseFloat(value);
    if (value.startsWith('"') && value.endsWith('"')) return value.slice(1, -1);
    if (value.startsWith("'") && value.endsWith("'")) return value.slice(1, -1);
    return value;
  }
}
