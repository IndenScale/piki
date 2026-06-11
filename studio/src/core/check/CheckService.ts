/**
 * CheckService — 检查结果服务（预留）
 *
 * 职责：加载 `piki check` 生成的检查报告，提供统计和过滤接口。
 * 当前为骨架实现，v0.2.0 时集成实际检查数据。
 */

import type { CheckReport, CheckResult } from '../../types/index.ts';

export interface ICheckService {
  /** 加载检查报告 */
  loadReport(report: CheckReport): void;

  /** 获取当前报告 */
  getReport(): CheckReport | null;

  /** 获取统计摘要 */
  getStats(): { passed: number; failed: number; warnings: number };

  /** 按严重级别过滤结果 */
  getResultsBySeverity(severity: 'error' | 'warning' | 'info'): CheckResult[];

  /** 按文件路径过滤结果 */
  getResultsByFile(filePath: string): CheckResult[];
}

export class CheckService implements ICheckService {
  private report: CheckReport | null = null;

  loadReport(report: CheckReport): void {
    this.report = report;
  }

  getReport(): CheckReport | null {
    return this.report;
  }

  getStats(): { passed: number; failed: number; warnings: number } {
    if (!this.report) {
      return { passed: 0, failed: 0, warnings: 0 };
    }
    return {
      passed: this.report.pass_count,
      failed: this.report.error_count,
      warnings: this.report.warning_count,
    };
  }

  getResultsBySeverity(severity: 'error' | 'warning' | 'info'): CheckResult[] {
    if (!this.report) return [];
    return this.report.results.filter((r) => r.severity === severity);
  }

  getResultsByFile(filePath: string): CheckResult[] {
    if (!this.report) return [];
    return this.report.results.filter((r) => r.file === filePath);
  }
}
