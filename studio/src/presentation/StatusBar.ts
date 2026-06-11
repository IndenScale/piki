import type { ICheckService } from '../core/check/CheckService.ts';

export class StatusBar {
  private checkService: ICheckService;
  private element: HTMLElement | null = null;
  private projectLabel: HTMLElement | null = null;
  private messageLabel: HTMLElement | null = null;
  private statsLabel: HTMLElement | null = null;

  constructor(checkService: ICheckService) {
    this.checkService = checkService;
  }

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-status-bar';
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'space-between';
    el.style.height = '28px';
    el.style.padding = '0 14px';
    el.style.background = 'var(--bg-tertiary)';
    el.style.borderTop = '1px solid var(--border-color)';
    el.style.fontSize = '11px';
    el.style.color = 'var(--text-secondary)';
    el.style.flexShrink = '0';
    el.style.gap = '16px';

    // Left: project name + status
    const left = document.createElement('div');
    left.style.display = 'flex';
    left.style.alignItems = 'center';
    left.style.gap = '8px';
    left.style.flex = '1';
    left.style.overflow = 'hidden';

    const dot = document.createElement('span');
    dot.textContent = '●';
    dot.style.color = 'var(--text-muted)';
    dot.style.fontSize = '8px';
    left.appendChild(dot);

    this.projectLabel = document.createElement('span');
    this.projectLabel.textContent = '未打开项目';
    this.projectLabel.style.whiteSpace = 'nowrap';
    this.projectLabel.style.overflow = 'hidden';
    this.projectLabel.style.textOverflow = 'ellipsis';
    left.appendChild(this.projectLabel);

    el.appendChild(left);

    // Center: message
    const center = document.createElement('div');
    center.style.display = 'flex';
    center.style.alignItems = 'center';
    center.style.justifyContent = 'center';
    center.style.flex = '2';

    this.messageLabel = document.createElement('span');
    this.messageLabel.textContent = '';
    this.messageLabel.style.color = 'var(--text-muted)';
    center.appendChild(this.messageLabel);

    el.appendChild(center);

    // Right: stats + help
    const right = document.createElement('div');
    right.style.display = 'flex';
    right.style.alignItems = 'center';
    right.style.gap = '12px';
    right.style.flex = '1';
    right.style.justifyContent = 'flex-end';

    this.statsLabel = document.createElement('span');
    this.statsLabel.textContent = '';
    right.appendChild(this.statsLabel);

    const helpBtn = document.createElement('button');
    helpBtn.textContent = '?';
    helpBtn.title = '快捷键与操作指南';
    helpBtn.style.width = '18px';
    helpBtn.style.height = '18px';
    helpBtn.style.borderRadius = '50%';
    helpBtn.style.border = '1px solid var(--border-color)';
    helpBtn.style.background = 'transparent';
    helpBtn.style.color = 'var(--text-muted)';
    helpBtn.style.fontSize = '11px';
    helpBtn.style.fontWeight = '600';
    helpBtn.style.cursor = 'pointer';
    helpBtn.style.display = 'flex';
    helpBtn.style.alignItems = 'center';
    helpBtn.style.justifyContent = 'center';
    helpBtn.style.padding = '0';
    helpBtn.style.lineHeight = '1';
    helpBtn.style.transition = 'all 0.15s';
    helpBtn.addEventListener('mouseenter', () => {
      helpBtn.style.borderColor = 'var(--info)';
      helpBtn.style.color = 'var(--info)';
    });
    helpBtn.addEventListener('mouseleave', () => {
      helpBtn.style.borderColor = 'var(--border-color)';
      helpBtn.style.color = 'var(--text-muted)';
    });
    helpBtn.addEventListener('click', () => this.showHelpModal());
    right.appendChild(helpBtn);

    el.appendChild(right);

    this.element = el;
    return el;
  }

  setProject(name: string): void {
    if (this.projectLabel) {
      this.projectLabel.textContent = name;
    }
    const dot = this.element?.querySelector('span:first-child');
    if (dot) {
      (dot as HTMLElement).style.color = 'var(--success)';
    }
  }

  setMessage(msg: string): void {
    if (this.messageLabel) {
      this.messageLabel.textContent = msg;
    }
  }

  setStats(collections: number, instances: number, sceneObjects: number): void {
    if (!this.statsLabel) return;
    const parts: string[] = [];
    if (collections > 0) parts.push(`集合 ${collections}`);
    if (instances > 0) parts.push(`实例 ${instances}`);
    if (sceneObjects > 0) parts.push(`场景对象 ${sceneObjects}`);
    this.statsLabel.textContent = parts.join('  ·  ');
  }

  refreshStats(): void {
    if (!this.statsLabel) return;
    const stats = this.checkService.getStats();
    const parts: string[] = [];
    if (stats.passed > 0) parts.push(`通过 ${stats.passed}`);
    if (stats.failed > 0) parts.push(`失败 ${stats.failed}`);
    if (stats.warnings > 0) parts.push(`警告 ${stats.warnings}`);
    this.statsLabel.textContent = parts.join('  ') || '';
  }

  private showHelpModal(): void {
    // Backdrop
    const backdrop = document.createElement('div');
    backdrop.style.position = 'fixed';
    backdrop.style.inset = '0';
    backdrop.style.background = 'rgba(0, 0, 0, 0.6)';
    backdrop.style.zIndex = '1000';
    backdrop.style.display = 'flex';
    backdrop.style.alignItems = 'center';
    backdrop.style.justifyContent = 'center';
    backdrop.style.backdropFilter = 'blur(4px)';

    // Modal
    const modal = document.createElement('div');
    modal.style.background = 'var(--bg-secondary)';
    modal.style.border = '1px solid var(--border-color)';
    modal.style.borderRadius = '10px';
    modal.style.width = '420px';
    modal.style.maxWidth = '90vw';
    modal.style.maxHeight = '80vh';
    modal.style.display = 'flex';
    modal.style.flexDirection = 'column';
    modal.style.overflow = 'hidden';
    modal.style.boxShadow = '0 20px 60px rgba(0,0,0,0.5)';

    // Header
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.justifyContent = 'space-between';
    header.style.padding = '14px 18px';
    header.style.borderBottom = '1px solid var(--border-color)';

    const title = document.createElement('span');
    title.textContent = '快捷键与操作指南';
    title.style.fontSize = '14px';
    title.style.fontWeight = '600';
    title.style.color = 'var(--text-primary)';
    header.appendChild(title);

    const closeBtn = document.createElement('button');
    closeBtn.textContent = '×';
    closeBtn.style.background = 'transparent';
    closeBtn.style.border = 'none';
    closeBtn.style.color = 'var(--text-muted)';
    closeBtn.style.fontSize = '20px';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.lineHeight = '1';
    closeBtn.style.padding = '0 4px';
    closeBtn.style.transition = 'color 0.15s';
    closeBtn.addEventListener('mouseenter', () => {
      closeBtn.style.color = 'var(--text-primary)';
    });
    closeBtn.addEventListener('mouseleave', () => {
      closeBtn.style.color = 'var(--text-muted)';
    });
    closeBtn.addEventListener('click', () => backdrop.remove());
    header.appendChild(closeBtn);

    modal.appendChild(header);

    // Content
    const content = document.createElement('div');
    content.style.padding = '18px';
    content.style.overflowY = 'auto';
    content.style.fontSize = '13px';
    content.style.lineHeight = '1.7';
    content.style.color = 'var(--text-secondary)';

    const sections = [
      {
        title: '3D 视口操作',
        items: [
          ['左键拖拽', '旋转视角'],
          ['右键拖拽', '平移视角'],
          ['滚轮滚动', '缩放视角'],
          ['左键点击对象', '选中对象'],
          ['点击空白处', '取消选中'],
          ['W / A / S / D', '前后左右移动（需焦点在预览区）'],
          ['Q / E', '垂直下降 / 上升'],
        ],
      },
      {
        title: '场景树',
        items: [
          ['点击实例', '选中对象并高亮'],
          ['点击空白', '取消选中'],
        ],
      },
      {
        title: '项目操作',
        items: [
          ['点击标题栏项目名', '打开本地项目目录'],
          ['', '支持加载包含 YAML 实例文件的 piki 项目'],
        ],
      },
    ];

    for (const section of sections) {
      const secTitle = document.createElement('div');
      secTitle.textContent = section.title;
      secTitle.style.fontSize = '12px';
      secTitle.style.fontWeight = '600';
      secTitle.style.color = 'var(--accent)';
      secTitle.style.marginTop = '14px';
      secTitle.style.marginBottom = '8px';
      secTitle.style.textTransform = 'uppercase';
      secTitle.style.letterSpacing = '0.5px';
      if (sections.indexOf(section) === 0) secTitle.style.marginTop = '0';
      content.appendChild(secTitle);

      for (const [key, val] of section.items) {
        if (!key && !val) continue;
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.alignItems = 'center';
        row.style.padding = '4px 0';
        row.style.borderBottom = '1px solid rgba(48, 54, 61, 0.3)';

        const keyEl = document.createElement('span');
        keyEl.textContent = key;
        keyEl.style.color = 'var(--text-primary)';
        keyEl.style.fontWeight = '500';

        const valEl = document.createElement('span');
        valEl.textContent = val;
        valEl.style.color = 'var(--text-muted)';

        row.appendChild(keyEl);
        row.appendChild(valEl);
        content.appendChild(row);
      }
    }

    modal.appendChild(content);
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    // Close on backdrop click
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) backdrop.remove();
    });

    // Close on Escape
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        backdrop.remove();
        document.removeEventListener('keydown', onKey);
      }
    };
    document.addEventListener('keydown', onKey);
  }
}
