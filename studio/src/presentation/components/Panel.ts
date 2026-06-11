/**
 * Panel — 可复用面板容器
 *
 * 结构：header（图标 + 标题）+ content
 */

export interface PanelOptions {
  title: string;
  icon?: string;
  iconColor?: string;
}

export interface PanelResult {
  root: HTMLElement;
  content: HTMLElement;
  setTitle(title: string): void;
}

export function createPanel(opts: PanelOptions): PanelResult {
  const root = document.createElement('div');
  root.className = 'piki-panel';
  root.style.display = 'flex';
  root.style.flexDirection = 'column';
  root.style.background = 'var(--bg-secondary)';
  root.style.overflow = 'hidden';

  // Header
  const header = document.createElement('div');
  header.className = 'piki-panel__header';
  header.style.display = 'flex';
  header.style.alignItems = 'center';
  header.style.gap = '8px';
  header.style.padding = '10px 14px';
  header.style.background = 'var(--bg-tertiary)';
  header.style.borderBottom = '1px solid var(--border-color)';
  header.style.flexShrink = '0';
  header.style.fontWeight = '600';
  header.style.fontSize = '13px';
  header.style.color = 'var(--text-primary)';
  header.style.userSelect = 'none';

  if (opts.icon) {
    const iconEl = document.createElement('span');
    iconEl.textContent = opts.icon;
    iconEl.style.display = 'inline-flex';
    iconEl.style.alignItems = 'center';
    iconEl.style.justifyContent = 'center';
    iconEl.style.width = '20px';
    iconEl.style.height = '20px';
    iconEl.style.borderRadius = '4px';
    iconEl.style.fontSize = '11px';
    iconEl.style.fontWeight = 'bold';
    iconEl.style.color = '#fff';
    iconEl.style.background = opts.iconColor || 'var(--accent)';
    header.appendChild(iconEl);
  }

  const titleEl = document.createElement('span');
  titleEl.textContent = opts.title;
  header.appendChild(titleEl);

  root.appendChild(header);

  // Content
  const content = document.createElement('div');
  content.className = 'piki-panel__content';
  content.style.flex = '1';
  content.style.overflowY = 'auto';
  content.style.overflowX = 'hidden';
  root.appendChild(content);

  return {
    root,
    content,
    setTitle(title: string) {
      titleEl.textContent = title;
    },
  };
}
