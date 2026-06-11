/**
 * Button — 统一按钮组件
 *
 * 变体：primary | secondary | ghost | icon
 */

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'icon';

export interface ButtonOptions {
  label: string;
  variant?: ButtonVariant;
  active?: boolean;
  title?: string;
  onClick: () => void;
}

export function createButton(opts: ButtonOptions): HTMLButtonElement {
  const btn = document.createElement('button');
  btn.textContent = opts.label;
  btn.title = opts.title || opts.label;
  btn.className = `piki-btn piki-btn--${opts.variant || 'secondary'}`;
  if (opts.active) btn.classList.add('piki-btn--active');

  applyBaseStyles(btn);
  applyVariantStyles(btn, opts.variant || 'secondary', opts.active);

  btn.addEventListener('click', opts.onClick);
  return btn;
}

function applyBaseStyles(btn: HTMLButtonElement): void {
  btn.style.display = 'inline-flex';
  btn.style.alignItems = 'center';
  btn.style.justifyContent = 'center';
  btn.style.gap = '4px';
  btn.style.border = 'none';
  btn.style.borderRadius = '6px';
  btn.style.fontSize = '12px';
  btn.style.fontWeight = '500';
  btn.style.cursor = 'pointer';
  btn.style.transition = 'all 0.15s ease';
  btn.style.whiteSpace = 'nowrap';
  btn.style.userSelect = 'none';
}

function applyVariantStyles(
  btn: HTMLButtonElement,
  variant: ButtonVariant,
  active?: boolean,
): void {
  const isActive = active || btn.classList.contains('piki-btn--active');

  switch (variant) {
    case 'primary':
      btn.style.padding = '6px 14px';
      btn.style.background = isActive ? 'var(--accent-hover)' : 'var(--accent)';
      btn.style.color = '#fff';
      btn.addEventListener('mouseenter', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'var(--accent-hover)';
        }
      });
      btn.addEventListener('mouseleave', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'var(--accent)';
        }
      });
      break;

    case 'secondary':
      btn.style.padding = '6px 14px';
      btn.style.background = isActive ? 'var(--accent)' : 'var(--bg-tertiary)';
      btn.style.color = isActive ? '#fff' : 'var(--text-primary)';
      btn.style.border = '1px solid var(--border-color)';
      btn.addEventListener('mouseenter', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'var(--bg-secondary)';
          btn.style.borderColor = 'var(--accent)';
        }
      });
      btn.addEventListener('mouseleave', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'var(--bg-tertiary)';
          btn.style.borderColor = 'var(--border-color)';
        }
      });
      break;

    case 'ghost':
      btn.style.padding = '6px 14px';
      btn.style.background = isActive ? 'var(--bg-tertiary)' : 'transparent';
      btn.style.color = isActive ? 'var(--accent)' : 'var(--text-secondary)';
      btn.addEventListener('mouseenter', () => {
        btn.style.background = 'var(--bg-tertiary)';
        btn.style.color = 'var(--text-primary)';
      });
      btn.addEventListener('mouseleave', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'transparent';
          btn.style.color = 'var(--text-secondary)';
        }
      });
      break;

    case 'icon':
      btn.style.padding = '6px 10px';
      btn.style.background = isActive ? 'var(--accent)' : 'var(--bg-tertiary)';
      btn.style.color = isActive ? '#fff' : 'var(--text-secondary)';
      btn.style.border = '1px solid var(--border-color)';
      btn.style.borderRadius = '6px';
      btn.addEventListener('mouseenter', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'var(--bg-secondary)';
          btn.style.borderColor = 'var(--accent)';
          btn.style.color = 'var(--text-primary)';
        }
      });
      btn.addEventListener('mouseleave', () => {
        if (!btn.classList.contains('piki-btn--active')) {
          btn.style.background = 'var(--bg-tertiary)';
          btn.style.borderColor = 'var(--border-color)';
          btn.style.color = 'var(--text-secondary)';
        }
      });
      break;
  }
}

export function setButtonActive(btn: HTMLButtonElement, active: boolean): void {
  if (active) {
    btn.classList.add('piki-btn--active');
    btn.style.background = 'var(--accent)';
    btn.style.color = '#fff';
    btn.style.borderColor = 'var(--accent)';
  } else {
    btn.classList.remove('piki-btn--active');
    btn.style.background = 'var(--bg-tertiary)';
    btn.style.color = 'var(--text-secondary)';
    btn.style.borderColor = 'var(--border-color)';
  }
}
