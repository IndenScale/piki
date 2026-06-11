import type { ISelectionService } from '../core/selection/SelectionService.ts';
import type { ISceneService } from '../core/scene/SceneService.ts';
import type { IThreeRenderer } from '../infrastructure/renderer/ThreeRenderer.ts';
import type { SceneObject } from '../types/index.ts';

export class Viewport {
  private selectionService: ISelectionService;
  private sceneService: ISceneService;
  private renderer: IThreeRenderer;
  private element: HTMLElement | null = null;
  private canvasContainer: HTMLElement | null = null;

  constructor(
    selectionService: ISelectionService,
    sceneService: ISceneService,
    renderer: IThreeRenderer,
  ) {
    this.selectionService = selectionService;
    this.sceneService = sceneService;
    this.renderer = renderer;

    // Subscribe to selection changes from other sources (e.g., SceneTree)
    this.selectionService.onChange((obj) => {
      if (obj) {
        this.renderer.highlightObject(obj.name);
      } else {
        this.renderer.clearHighlight();
      }
    });

    // Handle selection from 3D canvas
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
    el.style.background = '#0a0a1a';
    el.style.overflow = 'hidden';

    // Toolbar
    const toolbar = document.createElement('div');
    toolbar.className = 'viewport-toolbar';
    toolbar.style.position = 'absolute';
    toolbar.style.top = '12px';
    toolbar.style.left = '12px';
    toolbar.style.display = 'flex';
    toolbar.style.gap = '6px';
    toolbar.style.zIndex = '10';

    const btnOrbit = this.createToolButton('🔄 旋转', true);
    const btnPan = this.createToolButton('✋ 平移', false);
    const btnZoom = this.createToolButton('🔍 缩放', false);
    const btnFit = this.createToolButton('⊡ 适配', false);
    const btnWireframe = this.createToolButton('▧ 线框', false);

    const buttons = [btnOrbit, btnPan, btnZoom, btnFit, btnWireframe];

    btnOrbit.addEventListener('click', () => {
      this.renderer.setCameraMode('orbit');
      this.updateToolbar(buttons, btnOrbit);
    });
    btnPan.addEventListener('click', () => {
      this.renderer.setCameraMode('pan');
      this.updateToolbar(buttons, btnPan);
    });
    btnZoom.addEventListener('click', () => {
      this.renderer.setCameraMode('zoom');
      this.updateToolbar(buttons, btnZoom);
    });
    btnFit.addEventListener('click', () => this.renderer.fitView());
    btnWireframe.addEventListener('click', () => {
      const isWireframe = btnWireframe.classList.contains('active-wireframe');
      this.renderer.setWireframe(!isWireframe);
      btnWireframe.classList.toggle('active-wireframe', !isWireframe);
      btnWireframe.style.background = !isWireframe ? '#e94560' : 'rgba(22, 33, 62, 0.9)';
      btnWireframe.style.borderColor = !isWireframe ? '#e94560' : '#0f3460';
    });

    toolbar.appendChild(btnOrbit);
    toolbar.appendChild(btnPan);
    toolbar.appendChild(btnZoom);
    toolbar.appendChild(btnFit);
    toolbar.appendChild(btnWireframe);
    el.appendChild(toolbar);

    // Canvas container
    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '100%';
    this.canvasContainer = container;
    el.appendChild(container);

    // Info overlay
    const info = document.createElement('div');
    info.className = 'viewport-info';
    info.textContent = '左键: 旋转 | 右键: 平移 | 滚轮: 缩放 | 点击: 选择';
    info.style.position = 'absolute';
    info.style.bottom = '12px';
    info.style.left = '12px';
    info.style.background = 'rgba(22, 33, 62, 0.9)';
    info.style.border = '1px solid #0f3460';
    info.style.borderRadius = '6px';
    info.style.padding = '8px 12px';
    info.style.fontSize = '11px';
    info.style.color = '#888';
    info.style.pointerEvents = 'none';
    info.style.zIndex = '10';
    el.appendChild(info);

    this.element = el;
    return el;
  }

  /** 在 DOM 插入后初始化 Three.js 渲染器 */
  init(): void {
    if (this.canvasContainer) {
      this.renderer.mount(this.canvasContainer);
    }
  }

  /** 加载场景对象到 3D 视口 */
  loadScene(objects: SceneObject[]): void {
    this.renderer.loadScene(objects);
  }

  private createToolButton(label: string, active: boolean): HTMLButtonElement {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.className = active ? 'toolbar-btn active' : 'toolbar-btn';
    btn.style.background = active ? '#e94560' : 'rgba(22, 33, 62, 0.9)';
    btn.style.border = '1px solid #0f3460';
    btn.style.color = '#e0e0e0';
    btn.style.padding = '6px 12px';
    btn.style.borderRadius = '6px';
    btn.style.fontSize = '12px';
    btn.style.cursor = 'pointer';
    btn.style.transition = 'all 0.15s';
    btn.addEventListener('mouseenter', () => {
      if (!btn.classList.contains('active')) {
        btn.style.background = '#1a2744';
        btn.style.borderColor = '#e94560';
      }
    });
    btn.addEventListener('mouseleave', () => {
      if (!btn.classList.contains('active')) {
        btn.style.background = 'rgba(22, 33, 62, 0.9)';
        btn.style.borderColor = '#0f3460';
      }
    });
    return btn;
  }

  private updateToolbar(buttons: HTMLButtonElement[], active: HTMLButtonElement): void {
    for (const btn of buttons) {
      btn.classList.remove('active');
      btn.style.background = 'rgba(22, 33, 62, 0.9)';
      btn.style.borderColor = '#0f3460';
    }
    active.classList.add('active');
    active.style.background = '#e94560';
    active.style.borderColor = '#e94560';
  }
}
