export interface PikiInstance {
  id: string;
  family: string;
  model?: string;
  collection: string;
  source: string;
  raw: Record<string, unknown>;
  resolved: Record<string, unknown>;
  _validation_error?: string;
}

export interface PikiCollection {
  name: string;
  instances: PikiInstance[];
}

export interface PikiProject {
  name: string;
  version: string;
  root: string;
  collections: PikiCollection[];
  plugins: string[];
}

export interface CheckResult {
  rule_id: string;
  name: string;
  passed: boolean;
  message: string;
  file: string;
  severity: 'error' | 'warning' | 'info';
}

export interface CheckReport {
  passed: boolean;
  error_count: number;
  warning_count: number;
  pass_count: number;
  results: CheckResult[];
}

export interface SceneObject {
  name: string;
  displayName: string | null;
  type: 'rack' | 'device' | 'pdu' | 'collection' | 'group';
  depth: number;
  parent: SceneObject | null;
  children: SceneObject[];
  geometry: GeometryInfo | null;
}

export interface GeometryInfo {
  type: string;
  transform: number[]; // 16-element matrix4d
  color: { r: number; g: number; b: number };
  size: number;
}
