/**
 * ProjectService — 项目加载服务
 *
 * 职责：扫描目录、解析 YAML 实例文件、构建 PikiProject 模型。
 * 不依赖任何 DOM 或 Three.js API，可在 Node.js 环境中单元测试。
 */

import type { PikiProject, PikiInstance, PikiCollection } from '../../types/index.ts';
import type { IFileSystem, FileEntry } from '../../infrastructure/fs/FileSystem.ts';
import type { IYamlParser } from '../../infrastructure/parsers/YamlParser.ts';

export interface IProjectService {
  loadProject(dirHandle: FileSystemDirectoryHandle): Promise<PikiProject>;
}

export class ProjectService implements IProjectService {
  private fs: IFileSystem;
  private yamlParser: IYamlParser;

  constructor(fs: IFileSystem, yamlParser: IYamlParser) {
    this.fs = fs;
    this.yamlParser = yamlParser;
  }

  async loadProject(dirHandle: FileSystemDirectoryHandle): Promise<PikiProject> {
    const project: PikiProject = {
      name: dirHandle.name,
      version: '1.0.0',
      root: dirHandle.name,
      collections: [],
      plugins: [],
    };

    // Scan for YAML files recursively
    const files = await this.fs.scanDirectory(dirHandle, ['.yaml', '.yml']);

    // Group files by top-level directory (collection)
    const collectionMap = new Map<string, PikiInstance[]>();

    for (const file of files) {
      const collectionName = this._extractCollectionName(file.path);
      if (!collectionName) continue;

      const text = await this.fs.readFile(file.handle);
      const data = this.yamlParser.parse(text);

      if (data.id) {
        const instance: PikiInstance = {
          id: String(data.id),
          family: String(data.family || ''),
          model: data.model ? String(data.model) : undefined,
          collection: collectionName,
          source: file.name,
          raw: data,
          resolved: data,
        };

        if (!collectionMap.has(collectionName)) {
          collectionMap.set(collectionName, []);
        }
        collectionMap.get(collectionName)!.push(instance);
      }
    }

    // Convert map to sorted collections
    for (const [name, instances] of collectionMap) {
      project.collections.push({ name, instances });
    }
    project.collections.sort((a, b) => a.name.localeCompare(b.name));

    return project;
  }

  private _extractCollectionName(filePath: string): string | null {
    // filePath format: "collectionName/subdir/file.yaml" or "collectionName/file.yaml"
    const firstSlash = filePath.indexOf('/');
    if (firstSlash === -1) return null;
    return filePath.slice(0, firstSlash);
  }
}
