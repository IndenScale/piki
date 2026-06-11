/**
 * Utils — 通用工具函数
 *
 * 纯函数，无外部依赖，可在任何层级使用。
 */

/**
 * 格式化数字，保留 3 位小数并去除末尾零
 */
export function fmt(n: number): string {
  if (typeof n !== 'number') return String(n);
  return n.toFixed(3).replace(/\.?0+$/, '');
}

/**
 * 根据实例 ID 推断类型（启发式规则）
 */
export function inferTypeFromId(id: string): 'rack' | 'device' | 'pdu' | 'group' {
  const lower = id.toLowerCase();
  if (lower.startsWith('rack')) return 'rack';
  if (lower.startsWith('pdu')) return 'pdu';
  if (lower.startsWith('srv') || lower.startsWith('device')) return 'device';
  return 'group';
}

/**
 * 根据类型返回显示标签
 */
export function typeLabel(type: string): string {
  const labels: Record<string, string> = {
    rack: '机柜',
    device: '设备',
    pdu: 'PDU',
    collection: '集合',
    group: '组',
  };
  return labels[type] || type;
}

/**
 * 根据类型返回颜色
 */
export function typeColor(type: string): string {
  const colors: Record<string, string> = {
    rack: '#4a90d9',
    device: '#5cb85c',
    pdu: '#f0ad4e',
    collection: '#6c757d',
    group: '#6c757d',
  };
  return colors[type] || '#6c757d';
}

/**
 * 从 4x4 矩阵提取位置
 */
export function extractPosition(matrix: number[]): { x: number; y: number; z: number } {
  return {
    x: matrix[12] || 0,
    y: matrix[13] || 0,
    z: matrix[14] || 0,
  };
}

/**
 * 从 4x4 矩阵提取缩放
 */
export function extractScale(matrix: number[]): { x: number; y: number; z: number } {
  return {
    x: Math.sqrt(matrix[0] * matrix[0] + matrix[1] * matrix[1] + matrix[2] * matrix[2]) || 1,
    y: Math.sqrt(matrix[4] * matrix[4] + matrix[5] * matrix[5] + matrix[6] * matrix[6]) || 1,
    z: Math.sqrt(matrix[8] * matrix[8] + matrix[9] * matrix[9] + matrix[10] * matrix[10]) || 1,
  };
}
