/**
 * YamlParser — YAML 文本解析器
 *
 * 使用 js-yaml 库提供完整的 YAML 解析能力。
 */

import yaml from 'js-yaml';

export interface IYamlParser {
  parse(text: string): Record<string, unknown>;
}

export class SimpleYamlParser implements IYamlParser {
  parse(text: string): Record<string, unknown> {
    const result = yaml.load(text);
    if (result && typeof result === 'object' && !Array.isArray(result)) {
      return result as Record<string, unknown>;
    }
    return {};
  }
}
