import type { ISelectionService } from '../core/selection/SelectionService.ts';
import type { ISceneService } from '../core/scene/SceneService.ts';
import type { IThreeRenderer } from '../infrastructure/renderer/ThreeRenderer.ts';
import type { SceneObject } from '../types/index.ts';
import { createEmptyState } from './components/EmptyState.ts';

export class Viewport {
  private selectionService: ISelectionService;
  private sceneService: ISceneService;
  private renderer: IThreeRenderer;
  private element: HTMLElement | null = null;
  private canvasContainer: HTMLElement | null = null;
  private emptyOverlay: HTMLElement | null = null;

  constructor(
    selectionService: ISelectionService,
    sceneService: ISceneService,
    renderer: IThreeRenderer,
  ) {
    this.selectionService = selectionService;
    this.sceneService = sceneService;
    this.renderer = renderer;

    this.selectionService.onChange((obj) => {
      if (obj) {
        this.renderer.highlightObject(obj.name);
      } else {
        this.renderer.clearHighlight();
      }
    });

    this.renderer.onSelect((name) => {
      if (name) {
        const obj = this.sceneService.getObjectByName(name);
        this.selectionService.setSelected(obj);
      } else {
        this.selectionService.setSelected(null);
      }
    });
  }

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-viewport';
    el.style.flex = '1';
    el.style.position = 'relative';
    el.style.background = 'var(--bg-primary)';
    el.style.overflow = 'hidden';

    // Canvas container
    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '100%';
    container.tabIndex = 0;
    container.style.outline = 'none';
    container.style.borderRadius = 'inherit';
    this.canvasContainer = container;
    el.appendChild(container);

    // Empty state overlay
    this.emptyOverlay = createEmptyState({
      title: '暂无场景内容',
      subtitle: '打开项目以加载 3D 场景',
    });
    this.emptyOverlay.style.position = 'absolute';
    this.emptyOverlay.style.inset = '0';
    this.emptyOverlay.style.pointerEvents = 'none';
    this.emptyOverlay.style.zIndex = '5';
    this.emptyOverlay.style.display = 'flex';
    el.appendChild(this.emptyOverlay);

    this.element = el;
    return el;
  }

  init(): void {
    if (this.canvasContainer) {
      this.renderer.mount(this.canvasContainer);
      this.canvasContainer.focus();
    }
  }

  loadScene(objects: SceneObject[]): void {
    this.renderer.loadScene(objects);
    if (this.emptyOverlay) {
      this.emptyOverlay.style.display = objects.length > 0 ? 'none' : 'flex';
    }
  }
}
