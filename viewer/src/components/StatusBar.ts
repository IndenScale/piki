export class StatusBar {
  private element: HTMLElement | null = null;
  private projectLabel: HTMLElement | null = null;
  private messageLabel: HTMLElement | null = null;
  private statsLabel: HTMLElement | null = null;

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-status-bar';
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'space-between';
    el.style.height = '24px';
    el.style.padding = '0 12px';
    el.style.background = '#0f3460';
    el.style.borderTop = '1px solid #1a4a7a';
    el.style.fontSize = '11px';
    el.style.color = '#888';
    el.style.flexShrink = '0';

    // Left: project name
    this.projectLabel = document.createElement('span');
    this.projectLabel.textContent = '未打开项目';
    el.appendChild(this.projectLabel);

    // Center: message
    this.messageLabel = document.createElement('span');
    this.messageLabel.textContent = '';
    el.appendChild(this.messageLabel);

    // Right: stats
    this.statsLabel = document.createElement('span');
    this.statsLabel.textContent = '';
    el.appendChild(this.statsLabel);

    this.element = el;
    return el;
  }

  setProject(name: string): void {
    if (this.projectLabel) {
      this.projectLabel.textContent = `项目: ${name}`;
    }
  }

  setMessage(msg: string): void {
    if (this.messageLabel) {
      this.messageLabel.textContent = msg;
    }
  }

  setStats(passed: number, failed: number, warnings: number): void {
    if (this.statsLabel) {
      const parts: string[] = [];
      if (passed > 0) parts.push(`✅ ${passed}`);
      if (failed > 0) parts.push(`❌ ${failed}`);
      if (warnings > 0) parts.push(`⚠️ ${warnings}`);
      this.statsLabel.textContent = parts.join('  ') || '';
    }
  }
}
