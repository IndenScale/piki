/**
 * Badge — 状态徽标组件
 */

export type BadgeVariant = 'default' | 'rack' | 'device' | 'pdu' | 'collection' | 'accent' | 'success' | 'info';

const variantColors: Record<BadgeVariant, { bg: string; text: string }> = {
  default: { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)' },
  rack: { bg: 'rgba(88, 166, 255, 0.15)', text: '#58a6ff' },
  device: { bg: 'rgba(63, 185, 80, 0.15)', text: '#3fb950' },
  pdu: { bg: 'rgba(210, 153, 34, 0.15)', text: '#d29922' },
  collection: { bg: 'rgba(139, 148, 158, 0.15)', text: '#8b949e' },
  accent: { bg: 'rgba(233, 69, 96, 0.15)', text: '#e94560' },
  success: { bg: 'rgba(63, 185, 80, 0.15)', text: '#3fb950' },
  info: { bg: 'rgba(88, 166, 255, 0.15)', text: '#58a6ff' },
};

export function createBadge(text: string, variant: BadgeVariant = 'default'): HTMLElement {
  const el = document.createElement('span');
  el.textContent = text;
  el.className = 'piki-badge';

  const colors = variantColors[variant];
  el.style.display = 'inline-flex';
  el.style.alignItems = 'center';
  el.style.padding = '1px 6px';
  el.style.borderRadius = '10px';
  el.style.fontSize = '10px';
  el.style.fontWeight = '600';
  el.style.lineHeight = '16px';
  el.style.background = colors.bg;
  el.style.color = colors.text;
  el.style.flexShrink = '0';

  return el;
}
