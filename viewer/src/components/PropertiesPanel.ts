import type { SceneObject } from '../types/piki.ts';

export class PropertiesPanel {
  private element: HTMLElement | null = null;
  private content: HTMLElement | null = null;

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-properties-panel';
    el.style.display = 'flex';
    el.style.flexDirection = 'column';
    el.style.background = '#16213e';
    el.style.borderLeft = '1px solid #0f3460';
    el.style.overflow = 'hidden';

    // Header
    const header = document.createElement('div');
    header.className = 'sidebar-header';
    header.style.padding = '12px 16px';
    header.style.background = '#0f3460';
    header.style.fontWeight = '600';
    header.style.fontSize = '14px';
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.gap = '8px';
    header.style.flexShrink = '0';

    const icon = document.createElement('div');
    icon.textContent = 'i';
    icon.style.width = '20px';
    icon.style.height = '20px';
    icon.style.background = '#4a90d9';
    icon.style.borderRadius = '4px';
    icon.style.display = 'flex';
    icon.style.alignItems = 'center';
    icon.style.justifyContent = 'center';
    icon.style.fontSize = '12px';
    icon.style.fontWeight = 'bold';
    icon.style.color = 'white';

    const title = document.createElement('span');
    title.textContent = '属性面板';

    header.appendChild(icon);
    header.appendChild(title);
    el.appendChild(header);

    // Content
    const content = document.createElement('div');
    content.className = 'properties-content';
    content.style.flex = '1';
    content.style.overflowY = 'auto';
    content.style.padding = '16px';
    this.content = content;
    el.appendChild(content);

    this.renderEmpty();

    this.element = el;
    return el;
  }

  setObject(obj: SceneObject | null): void {
    if (!this.content) return;
    this.content.innerHTML = '';

    if (!obj) {
      this.renderEmpty();
      return;
    }

    // Basic Info
    this.content.appendChild(this.createSection('基本信息', [
      { key: 'ID', value: obj.name },
      { key: '显示名称', value: obj.displayName || '-' },
      { key: '类型', value: this.typeLabel(obj.type) },
    ]));

    // Geometry
    if (obj.geometry) {
      const geo = obj.geometry;
      const mat = new Float32Array(geo.transform);
      const pos = { x: mat[12], y: mat[13], z: mat[14] };
      const scale = {
        x: Math.sqrt(mat[0] * mat[0] + mat[1] * mat[1] + mat[2] * mat[2]),
        y: Math.sqrt(mat[4] * mat[4] + mat[5] * mat[5] + mat[6] * mat[6]),
        z: Math.sqrt(mat[8] * mat[8] + mat[9] * mat[9] + mat[10] * mat[10]),
      };

      this.content.appendChild(this.createSection('几何信息', [
        { key: '位置 X', value: this.fmt(pos.x), valClass: 'number' },
        { key: '位置 Y', value: this.fmt(pos.y), valClass: 'number' },
        { key: '位置 Z', value: this.fmt(pos.z), valClass: 'number' },
        { key: '缩放 X', value: this.fmt(scale.x), valClass: 'dim' },
        { key: '缩放 Y', value: this.fmt(scale.y), valClass: 'dim' },
        { key: '缩放 Z', value: this.fmt(scale.z), valClass: 'dim' },
        { key: '尺寸', value: `${this.fmt(scale.x * 1000)} × ${this.fmt(scale.y * 1000)} × ${this.fmt(scale.z * 1000)} mm`, valClass: 'dim' },
      ]));

      // Appearance
      const colorSection = this.createSection('外观', [
        { key: '颜色', value: `RGB(${this.fmt(geo.color.r)}, ${this.fmt(geo.color.g)}, ${this.fmt(geo.color.b)})` },
      ]);
      const previewRow = document.createElement('div');
      previewRow.className = 'prop-row';
      previewRow.style.display = 'flex';
      previewRow.style.justifyContent = 'space-between';
      previewRow.style.alignItems = 'center';
      previewRow.style.padding = '6px 0';
      previewRow.style.fontSize = '13px';
      previewRow.style.borderBottom = '1px solid rgba(15, 52, 96, 0.3)';

      const previewKey = document.createElement('span');
      previewKey.className = 'prop-key';
      previewKey.textContent = '预览';
      previewKey.style.color = '#888';

      const previewVal = document.createElement('span');
      previewVal.className = 'prop-val';
      previewVal.style.display = 'inline-block';
      previewVal.style.width = '20px';
      previewVal.style.height = '20px';
      previewVal.style.background = `rgb(${Math.round(geo.color.r * 255)},${Math.round(geo.color.g * 255)},${Math.round(geo.color.b * 255)})`;
      previewVal.style.borderRadius = '3px';
      previewVal.style.border = '1px solid #444';

      previewRow.appendChild(previewKey);
      previewRow.appendChild(previewVal);
      colorSection.appendChild(previewRow);
      this.content.appendChild(colorSection);
    }

    // Hierarchy
    if (obj.children.length > 0) {
      const childRows = obj.children.map((child) => ({
        key: child.displayName || child.name,
        value: this.typeLabel(child.type),
      }));
      this.content.appendChild(this.createSection('子对象', childRows));
    }
  }

  private renderEmpty(): void {
    if (!this.content) return;
    const empty = document.createElement('div');
    empty.className = 'no-selection';
    empty.innerHTML = '在场景树或 3D 视图中选择一个对象<br>查看详细信息';
    empty.style.textAlign = 'center';
    empty.style.color = '#666';
    empty.style.padding = '40px 20px';
    empty.style.fontSize = '13px';
    this.content.appendChild(empty);
  }

  private createSection(title: string, rows: { key: string; value: string; valClass?: string }[]): HTMLElement {
    const section = document.createElement('div');
    section.className = 'prop-section';
    section.style.marginBottom = '20px';

    const sectionTitle = document.createElement('div');
    sectionTitle.className = 'prop-section-title';
    sectionTitle.textContent = title;
    sectionTitle.style.fontSize = '12px';
    sectionTitle.style.fontWeight = '600';
    sectionTitle.style.color = '#e94560';
    sectionTitle.style.textTransform = 'uppercase';
    sectionTitle.style.letterSpacing = '0.5px';
    sectionTitle.style.marginBottom = '10px';
    sectionTitle.style.paddingBottom = '6px';
    sectionTitle.style.borderBottom = '1px solid #0f3460';
    section.appendChild(sectionTitle);

    for (const row of rows) {
      const rowEl = document.createElement('div');
      rowEl.className = 'prop-row';
      rowEl.style.display = 'flex';
      rowEl.style.justifyContent = 'space-between';
      rowEl.style.alignItems = 'center';
      rowEl.style.padding = '6px 0';
      rowEl.style.fontSize = '13px';
      rowEl.style.borderBottom = '1px solid rgba(15, 52, 96, 0.3)';

      const keyEl = document.createElement('span');
      keyEl.className = 'prop-key';
      keyEl.textContent = row.key;
      keyEl.style.color = '#888';

      const valEl = document.createElement('span');
      valEl.className = `prop-val ${row.valClass || ''}`;
      valEl.textContent = row.value;
      valEl.style.color = '#e0e0e0';
      valEl.style.fontWeight = '500';
      if (row.valClass === 'number') {
        valEl.style.color = '#5cb85c';
        valEl.style.fontFamily = "'SF Mono', monospace";
      } else if (row.valClass === 'dim') {
        valEl.style.color = '#4a90d9';
        valEl.style.fontFamily = "'SF Mono', monospace";
      }

      rowEl.appendChild(keyEl);
      rowEl.appendChild(valEl);
      section.appendChild(rowEl);
    }

    return section;
  }

  private typeLabel(type: string): string {
    const labels: Record<string, string> = {
      rack: '机柜',
      device: '设备',
      pdu: 'PDU',
      collection: '集合',
      group: '组',
    };
    return labels[type] || type;
  }

  private fmt(n: number): string {
    if (typeof n !== 'number') return String(n);
    return n.toFixed(3).replace(/\.?0+$/, '');
  }
}
