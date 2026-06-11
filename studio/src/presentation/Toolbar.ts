import type { IProjectService } from '../core/project/ProjectService.ts';

export class Toolbar {
  private projectService: IProjectService;
  private onProjectOpened: (dirHandle: FileSystemDirectoryHandle) => void;

  private element: HTMLElement | null = null;
  private projectNameEl: HTMLElement | null = null;

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
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.height = '40px';
    el.style.padding = '0 14px';
    el.style.background = 'var(--bg-secondary)';
    el.style.borderBottom = '1px solid var(--border-color)';
    el.style.flexShrink = '0';
    el.style.gap = '10px';

    const brand = document.createElement('span');
    brand.textContent = 'Piki Studio';
    brand.style.fontSize = '14px';
    brand.style.fontWeight = '600';
    brand.style.color = 'var(--text-primary)';
    brand.style.flexShrink = '0';
    brand.style.userSelect = 'none';
    el.appendChild(brand);

    const divider = document.createElement('span');
    divider.textContent = '|';
    divider.style.color = 'var(--border-color)';
    divider.style.fontSize = '12px';
    divider.style.flexShrink = '0';
    divider.style.userSelect = 'none';
    el.appendChild(divider);

    this.projectNameEl = document.createElement('span');
    this.projectNameEl.textContent = '点击打开项目';
    this.projectNameEl.style.fontSize = '13px';
    this.projectNameEl.style.color = 'var(--text-muted)';
    this.projectNameEl.style.fontWeight = '400';
    this.projectNameEl.style.overflow = 'hidden';
    this.projectNameEl.style.textOverflow = 'ellipsis';
    this.projectNameEl.style.whiteSpace = 'nowrap';
    this.projectNameEl.style.cursor = 'pointer';
    this.projectNameEl.style.transition = 'color 0.15s';
    this.projectNameEl.addEventListener('mouseenter', () => {
      if (!this.projectNameEl?.dataset.project) {
        this.projectNameEl!.style.color = 'var(--text-secondary)';
      }
    });
    this.projectNameEl.addEventListener('mouseleave', () => {
      if (!this.projectNameEl?.dataset.project) {
        this.projectNameEl!.style.color = 'var(--text-muted)';
      }
    });
    this.projectNameEl.addEventListener('click', () => this.handleOpenProject());
    el.appendChild(this.projectNameEl);

    this.element = el;
    return el;
  }

  setProjectName(name: string | null): void {
    if (this.projectNameEl) {
      if (name) {
        this.projectNameEl.textContent = name;
        this.projectNameEl.style.color = 'var(--text-secondary)';
        this.projectNameEl.dataset.project = name;
        this.projectNameEl.style.cursor = 'default';
      } else {
        this.projectNameEl.textContent = '点击打开项目';
        this.projectNameEl.style.color = 'var(--text-muted)';
        delete this.projectNameEl.dataset.project;
        this.projectNameEl.style.cursor = 'pointer';
      }
    }
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
}
