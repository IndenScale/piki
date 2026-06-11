/**
 * App — Shell 应用容器
 *
 * 职责：
 * 1. 组装三层架构的所有依赖（依赖注入）
 * 2. 编排布局（Toolbar | SceneTree | Viewport | PropertiesPanel | StatusBar）
 * 3. 协调组件生命周期（mount → init → load → update）
 * 4. 处理跨层事件（项目加载 → 场景加载 → 状态更新）
 */

import { Toolbar } from '../presentation/Toolbar.ts';
import { SceneTree } from '../presentation/SceneTree.ts';
import { Viewport } from '../presentation/Viewport.ts';
import { PropertiesPanel } from '../presentation/PropertiesPanel.ts';
import { StatusBar } from '../presentation/StatusBar.ts';

import { ProjectService } from '../core/project/ProjectService.ts';
import { SceneService } from '../core/scene/SceneService.ts';
import { SelectionService } from '../core/selection/SelectionService.ts';
import { CheckService } from '../core/check/CheckService.ts';

import { BrowserFileSystem } from '../infrastructure/fs/FileSystem.ts';
import { SimpleYamlParser } from '../infrastructure/parsers/YamlParser.ts';
import { SimpleUsdaParser } from '../infrastructure/parsers/UsdaParser.ts';
import { ThreeRenderer } from '../infrastructure/renderer/ThreeRenderer.ts';

import type { PikiProject } from '../types/index.ts';

export class App {
  private root: HTMLElement;

  // ─── Services (Core Layer) ───
  private projectService: ProjectService;
  private sceneService: SceneService;
  private selectionService: SelectionService;
  private checkService: CheckService;

  // ─── Components (Presentation Layer) ───
  private toolbar: Toolbar;
  private sceneTree: SceneTree;
  private viewport: Viewport;
  private propertiesPanel: PropertiesPanel;
  private statusBar: StatusBar;

  // ─── State ───
  private currentProject: PikiProject | null = null;

  constructor(root: HTMLElement) {
    this.root = root;

    // ─── Infrastructure Layer ───
    const fileSystem = new BrowserFileSystem();
    const yamlParser = new SimpleYamlParser();
    const usdaParser = new SimpleUsdaParser();
    const threeRenderer = new ThreeRenderer();

    // ─── Core Layer ───
    this.projectService = new ProjectService(fileSystem, yamlParser);
    this.sceneService = new SceneService(usdaParser);
    this.selectionService = new SelectionService();
    this.checkService = new CheckService();

    // ─── Presentation Layer ───
    this.toolbar = new Toolbar(
      this.projectService,
      this.handleOpenProject.bind(this),
    );
    this.sceneTree = new SceneTree(this.selectionService);
    this.viewport = new Viewport(
      this.selectionService,
      this.sceneService,
      threeRenderer,
    );
    this.propertiesPanel = new PropertiesPanel(this.selectionService);
    this.statusBar = new StatusBar(this.checkService);
  }

  mount(): void {
    this.root.style.display = 'flex';
    this.root.style.flexDirection = 'column';
    this.root.style.width = '100%';
    this.root.style.height = '100%';

    // Toolbar
    this.root.appendChild(this.toolbar.render());

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
    rightSidebar.style.width = '280px';
    rightSidebar.style.minWidth = '220px';
    rightSidebar.style.maxWidth = '450px';
    rightSidebar.style.resize = 'horizontal';
    main.appendChild(rightSidebar);

    this.root.appendChild(main);

    // Status bar
    this.root.appendChild(this.statusBar.render());

    // Initialize viewport after DOM insertion
    this.viewport.init();
  }

  // ─── Event Handlers ───

  private async handleOpenProject(dirHandle: FileSystemDirectoryHandle): Promise<void> {
    this.statusBar.setMessage('正在加载项目...');
    this.toolbar.setProjectName(null);

    try {
      // 1. Load project via Core Layer
      const project = await this.projectService.loadProject(dirHandle);
      this.currentProject = project;

      // 2. Update SceneTree
      this.sceneTree.setProject(project);
      this.toolbar.setProjectName(project.name);
      this.statusBar.setProject(project.name);

      // 3. Try to load scene.usda, fallback to instance placeholders
      await this.loadScene(dirHandle, project);
    } catch (err) {
      console.error('Failed to load project:', err);
      this.statusBar.setMessage('加载项目失败: ' + (err as Error).message);
    }
  }

  private async loadScene(dirHandle: FileSystemDirectoryHandle, project: PikiProject): Promise<void> {
    let hasUsda = false;

    try {
      const fileHandle = await dirHandle.getFileHandle('scene.usda');
      const file = await fileHandle.getFile();
      const text = await file.text();

      // Parse via Core Layer
      this.sceneService.loadFromUsda(text);
      hasUsda = true;
      this.statusBar.setMessage('scene.usda 已加载');
    } catch {
      // scene.usda not found — generate placeholders from instances
      this.sceneService.loadFromInstances(project.collections);
      this.statusBar.setMessage('已从实例生成占位场景');
    }

    // Render via Presentation Layer
    const objects = this.sceneService.getAllObjects();
    this.viewport.loadScene(objects);

    // Update stats
    const totalInstances = project.collections.reduce((s, c) => s + c.instances.length, 0);
    this.statusBar.setStats(
      project.collections.length,
      totalInstances,
      objects.filter((o) => o.geometry !== null).length,
    );
  }
}
