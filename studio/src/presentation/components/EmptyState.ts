/**
 * EmptyState — 空状态占位组件
 */

export interface EmptyStateOptions {
  icon?: string;
  title: string;
  subtitle?: string;
}

export function createEmptyState(opts: EmptyStateOptions): HTMLElement {
  const el = document.createElement('div');
  el.className = 'piki-empty-state';
  el.style.display = 'flex';
  el.style.flexDirection = 'column';
  el.style.alignItems = 'center';
  el.style.justifyContent = 'center';
  el.style.padding = '40px 20px';
  el.style.textAlign = 'center';
  el.style.gap = '8px';

  if (opts.icon) {
    const icon = document.createElement('div');
    icon.textContent = opts.icon;
    icon.style.fontSize = '32px';
    icon.style.opacity = '0.3';
    icon.style.marginBottom = '4px';
    el.appendChild(icon);
  }

  const title = document.createElement('div');
  title.textContent = opts.title;
  title.style.fontSize = '13px';
  title.style.fontWeight = '500';
  title.style.color = 'var(--text-secondary)';
  el.appendChild(title);

  if (opts.subtitle) {
    const sub = document.createElement('div');
    sub.textContent = opts.subtitle;
    sub.style.fontSize = '12px';
    sub.style.color = 'var(--text-muted)';
    el.appendChild(sub);
  }

  return el;
}
