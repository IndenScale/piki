import { Toolbar } from './Toolbar.ts';
import { SceneTree } from './SceneTree.ts';
import { Viewport } from './Viewport.ts';
import { PropertiesPanel } from './PropertiesPanel.ts';
import { StatusBar } from './StatusBar.ts';
import type { PikiProject, PikiInstance, SceneObject } from '../types/piki.ts';

export class App {
  private root: HTMLElement;
  private toolbar: Toolbar;
  private sceneTree: SceneTree;
  private viewport: Viewport;
  private propertiesPanel: PropertiesPanel;
  private statusBar: StatusBar;
  private project: PikiProject | null = null;
  private selectedObject: SceneObject | null = null;

  constructor(root: HTMLElement) {
    this.root = root;
    this.toolbar = new Toolbar(this.onOpenProject.bind(this));
    this.sceneTree = new SceneTree(this.onSelectObject.bind(this));
    this.viewport = new Viewport(this.onSelectObject.bind(this));
    this.propertiesPanel = new PropertiesPanel();
    this.statusBar = new StatusBar();
  }

  mount(): void {
    this.root.style.display = 'flex';
    this.root.style.flexDirection = 'column';
    this.root.style.width = '100%';
    this.root.style.height = '100%';

    // Toolbar
    const toolbarEl = this.toolbar.render();
    this.root.appendChild(toolbarEl);

    // Main content area
    const main = document.createElement('div');
    main.style.display = 'flex';
    main.style.flex = '1';
    main.style.overflow = 'hidden';

    // Left sidebar - Scene Tree
    const leftSidebar = this.sceneTree.render();
    leftSidebar.style.width = '260px';
    leftSidebar.style.minWidth = '200px';
    leftSidebar.style.maxWidth = '400px';
    leftSidebar.style.resize = 'horizontal';
    main.appendChild(leftSidebar);

    // Center - Viewport
    const viewportEl = this.viewport.render();
    viewportEl.style.flex = '1';
    main.appendChild(viewportEl);

    // Right sidebar - Properties
    const rightSidebar = this.propertiesPanel.render();
    rightSidebar.style.width = '300px';
    rightSidebar.style.minWidth = '250px';
    rightSidebar.style.maxWidth = '500px';
    rightSidebar.style.resize = 'horizontal';
    main.appendChild(rightSidebar);

    this.root.appendChild(main);

    // Status bar
    const statusEl = this.statusBar.render();
    this.root.appendChild(statusEl);

    // Initialize viewport after DOM insertion
    this.viewport.init();
  }

  private async onOpenProject(): Promise<void> {
    try {
      const dirHandle = await window.showDirectoryPicker();
      await this.loadProject(dirHandle);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Failed to open project:', err);
        this.statusBar.setMessage('打开项目失败: ' + (err as Error).message);
      }
    }
  }

  private async loadProject(dirHandle: FileSystemDirectoryHandle): Promise<void> {
    this.statusBar.setMessage('正在加载项目...');

    const project: PikiProject = {
      name: dirHandle.name,
      version: '1.0.0',
      root: dirHandle.name,
      collections: [],
      plugins: [],
    };

    // Scan directories for YAML files
    for await (const [name, handle] of dirHandle.entries()) {
      if (handle.kind === 'directory' && name !== 'library' && !name.startsWith('.')) {
        const instances: PikiInstance[] = [];
        await this.scanDirectory(handle as FileSystemDirectoryHandle, name, instances);
        if (instances.length > 0) {
          project.collections.push({ name, instances });
        }
      }
    }

    this.project = project;
    this.sceneTree.setProject(project);
    this.statusBar.setProject(project.name);
    this.statusBar.setMessage(`已加载 ${project.collections.length} 个集合, ${project.collections.reduce((sum, c) => sum + c.instances.length, 0)} 个实例`);

    // Try to load scene.usda if exists
    await this.loadSceneFile(dirHandle);
  }

  private async scanDirectory(
    dirHandle: FileSystemDirectoryHandle,
    collection: string,
    instances: PikiInstance[],
  ): Promise<void> {
    for await (const [name, handle] of dirHandle.entries()) {
      if (handle.kind === 'directory') {
        await this.scanDirectory(handle as FileSystemDirectoryHandle, collection, instances);
      } else if (name.endsWith('.yaml') || name.endsWith('.yml')) {
        const file = await (handle as FileSystemFileHandle).getFile();
        const text = await file.text();
        try {
          const data = this.parseYaml(text);
          if (data.id) {
            instances.push({
              id: String(data.id),
              family: String(data.family || ''),
              model: data.model ? String(data.model) : undefined,
              collection,
              source: name,
              raw: data,
              resolved: data,
            });
          }
        } catch {
          // skip invalid yaml
        }
      }
    }
  }

  private parseYaml(text: string): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    const lines = text.split('\n');
    let indentStack: { key: string; indent: number }[] = [];

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
          result[key] = this.parseValue(value);
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
          target[key] = this.parseValue(value);
        } else {
          target[key] = {};
        }
        indentStack.push({ key, indent });
      }
    }

    return result;
  }

  private parseValue(value: string): unknown {
    if (value === 'true') return true;
    if (value === 'false') return false;
    if (value === 'null' || value === '~') return null;
    if (/^-?\d+$/.test(value)) return parseInt(value, 10);
    if (/^-?\d+\.\d+$/.test(value)) return parseFloat(value);
    if (value.startsWith('"') && value.endsWith('"')) return value.slice(1, -1);
    if (value.startsWith("'") && value.endsWith("'")) return value.slice(1, -1);
    return value;
  }

  private async loadSceneFile(dirHandle: FileSystemDirectoryHandle): Promise<void> {
    try {
      const fileHandle = await dirHandle.getFileHandle('scene.usda');
      const file = await fileHandle.getFile();
      const text = await file.text();
      this.viewport.loadUsda(text);
    } catch {
      // scene.usda not found, that's ok
    }
  }

  private onSelectObject(obj: SceneObject | null): void {
    this.selectedObject = obj;
    this.sceneTree.selectObject(obj);
    this.propertiesPanel.setObject(obj);
    if (obj) {
      this.viewport.highlightObject(obj.name);
    }
  }
}
