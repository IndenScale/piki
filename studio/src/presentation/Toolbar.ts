import type { IProjectService } from '../core/project/ProjectService.ts';

export class Toolbar {
  private projectService: IProjectService;
  private onProjectOpened: (dirHandle: FileSystemDirectoryHandle) => void;
  private element: HTMLElement | null = null;

  constructor(
    projectService: IProjectService,
    onProjectOpened: (dirHandle: FileSystemDirectoryHandle) => void,
  ) {
    this.projectService = projectService;
    this.onProjectOpened = onProjectOpened;
  }

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-toolbar';
    this.applyStyles(el);

    // Logo + title
    const brand = document.createElement('div');
    brand.style.display = 'flex';
    brand.style.alignItems = 'center';
    brand.style.gap = '8px';

    const logo = document.createElement('div');
    logo.textContent = 'P';
    logo.style.width = '24px';
    logo.style.height = '24px';
    logo.style.background = '#e94560';
    logo.style.borderRadius = '4px';
    logo.style.display = 'flex';
    logo.style.alignItems = 'center';
    logo.style.justifyContent = 'center';
    logo.style.fontSize = '14px';
    logo.style.fontWeight = 'bold';
    logo.style.color = 'white';

    const title = document.createElement('span');
    title.textContent = 'Piki Studio';
    title.style.fontSize = '14px';
    title.style.fontWeight = '600';
    title.style.color = '#e0e0e0';

    brand.appendChild(logo);
    brand.appendChild(title);
    el.appendChild(brand);

    // Actions
    const actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.gap = '8px';

    const openBtn = this.createButton('📁 打开项目', () => this.handleOpenProject());
    actions.appendChild(openBtn);

    el.appendChild(actions);
    this.element = el;
    return el;
  }

  private async handleOpenProject(): Promise<void> {
    try {
      const dirHandle = await window.showDirectoryPicker();
      this.onProjectOpened(dirHandle);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Failed to open project:', err);
      }
    }
  }

  private createButton(label: string, onClick: () => void): HTMLButtonElement {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.style.background = '#0f3460';
    btn.style.border = '1px solid #1a4a7a';
    btn.style.color = '#e0e0e0';
    btn.style.padding = '6px 14px';
    btn.style.borderRadius = '4px';
    btn.style.fontSize = '12px';
    btn.style.cursor = 'pointer';
    btn.style.transition = 'all 0.15s';
    btn.addEventListener('mouseenter', () => {
      btn.style.background = '#1a4a7a';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.background = '#0f3460';
    });
    btn.addEventListener('click', onClick);
    return btn;
  }

  private applyStyles(el: HTMLElement): void {
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'space-between';
    el.style.height = '40px';
    el.style.padding = '0 16px';
    el.style.background = '#16213e';
    el.style.borderBottom = '1px solid #0f3460';
    el.style.flexShrink = '0';
  }
}
