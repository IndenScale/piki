import type { ISelectionService } from '../core/selection/SelectionService.ts';
import type { SceneObject } from '../types/index.ts';
import { typeLabel, fmt, extractPosition, extractScale } from '../utils/index.ts';
import { createPanel } from './components/Panel.ts';
import { createBadge } from './components/Badge.ts';
import { createEmptyState } from './components/EmptyState.ts';

export class PropertiesPanel {
  private selectionService: ISelectionService;
  private element: HTMLElement | null = null;
  private content: HTMLElement | null = null;
  private panel: ReturnType<typeof createPanel> | null = null;

  constructor(selectionService: ISelectionService) {
    this.selectionService = selectionService;
    this.selectionService.onChange((obj) => {
      this.setObject(obj);
    });
  }

  render(): HTMLElement {
    this.panel = createPanel({ title: '属性面板' });
    this.element = this.panel.root;
    this.element.style.borderLeft = '1px solid var(--border-color)';

    this.content = this.panel.content;
    this.content.style.padding = '12px';

    this.renderEmpty();

    return this.element;
  }

  setObject(obj: SceneObject | null): void {
    if (!this.content) return;
    this.content.innerHTML = '';

    if (!obj) {
      this.renderEmpty();
      return;
    }

    // Type badge at top
    const typeBadge = createBadge(typeLabel(obj.type), obj.type as 'rack' | 'device' | 'pdu' | 'collection');
    typeBadge.style.marginBottom = '12px';
    this.content.appendChild(typeBadge);

    // Basic Info
    this.content.appendChild(this.createSection('基本信息', [
      { key: 'ID', value: obj.name },
      { key: '显示名称', value: obj.displayName || '-' },
    ]));

    // Geometry
    if (obj.geometry) {
      const geo = obj.geometry;
      const pos = extractPosition(geo.transform);
      const scale = extractScale(geo.transform);

      this.content.appendChild(this.createSection('几何信息', [
        { key: '位置 X', value: fmt(pos.x), valClass: 'number' },
        { key: '位置 Y', value: fmt(pos.y), valClass: 'number' },
        { key: '位置 Z', value: fmt(pos.z), valClass: 'number' },
        { key: '缩放 X', value: fmt(scale.x), valClass: 'dim' },
        { key: '缩放 Y', value: fmt(scale.y), valClass: 'dim' },
        { key: '缩放 Z', value: fmt(scale.z), valClass: 'dim' },
        { key: '尺寸', value: `${fmt(scale.x * 1000)} × ${fmt(scale.y * 1000)} × ${fmt(scale.z * 1000)} mm`, valClass: 'dim' },
      ]));

      // Appearance
      const colorSection = this.createSection('外观', [
        { key: '颜色', value: `RGB(${fmt(geo.color.r)}, ${fmt(geo.color.g)}, ${fmt(geo.color.b)})` },
      ]);

      const previewRow = document.createElement('div');
      previewRow.style.display = 'flex';
      previewRow.style.justifyContent = 'space-between';
      previewRow.style.alignItems = 'center';
      previewRow.style.padding = '6px 0';
      previewRow.style.fontSize = '13px';
      previewRow.style.borderBottom = '1px solid var(--border-color)';

      const previewKey = document.createElement('span');
      previewKey.textContent = '预览';
      previewKey.style.color = 'var(--text-secondary)';
      previewKey.style.fontSize = '12px';

      const previewVal = document.createElement('span');
      previewVal.style.display = 'inline-block';
      previewVal.style.width = '20px';
      previewVal.style.height = '20px';
      previewVal.style.background = `rgb(${Math.round(geo.color.r * 255)},${Math.round(geo.color.g * 255)},${Math.round(geo.color.b * 255)})`;
      previewVal.style.borderRadius = '4px';
      previewVal.style.border = '1px solid var(--border-color)';
      previewVal.style.boxShadow = 'inset 0 0 0 1px rgba(0,0,0,0.2)';

      previewRow.appendChild(previewKey);
      previewRow.appendChild(previewVal);
      colorSection.appendChild(previewRow);
      this.content.appendChild(colorSection);
    }

    // Hierarchy
    if (obj.children.length > 0) {
      const childRows = obj.children.map((child) => ({
        key: child.displayName || child.name,
        value: typeLabel(child.type),
      }));
      this.content.appendChild(this.createSection('子对象', childRows));
    }
  }

  private renderEmpty(): void {
    if (!this.content) return;
    this.content.appendChild(
      createEmptyState({
        title: '未选择对象',
        subtitle: '在场景树或 3D 视图中点击对象',
      }),
    );
  }

  private createSection(title: string, rows: { key: string; value: string; valClass?: string }[]): HTMLElement {
    const section = document.createElement('div');
    section.style.marginBottom = '16px';

    const sectionTitle = document.createElement('div');
    sectionTitle.textContent = title;
    sectionTitle.style.fontSize = '11px';
    sectionTitle.style.fontWeight = '600';
    sectionTitle.style.color = 'var(--accent)';
    sectionTitle.style.textTransform = 'uppercase';
    sectionTitle.style.letterSpacing = '0.8px';
    sectionTitle.style.marginBottom = '8px';
    sectionTitle.style.paddingBottom = '6px';
    sectionTitle.style.borderBottom = '1px solid var(--border-color)';
    section.appendChild(sectionTitle);

    for (const row of rows) {
      const rowEl = document.createElement('div');
      rowEl.style.display = 'flex';
      rowEl.style.justifyContent = 'space-between';
      rowEl.style.alignItems = 'center';
      rowEl.style.padding = '5px 0';
      rowEl.style.fontSize = '12px';
      rowEl.style.borderBottom = '1px solid rgba(48, 54, 61, 0.4)';

      const keyEl = document.createElement('span');
      keyEl.textContent = row.key;
      keyEl.style.color = 'var(--text-secondary)';
      keyEl.style.fontSize = '12px';

      const valEl = document.createElement('span');
      valEl.textContent = row.value;
      valEl.style.color = 'var(--text-primary)';
      valEl.style.fontWeight = '500';
      valEl.style.fontSize = '12px';
      if (row.valClass === 'number') {
        valEl.style.color = 'var(--success)';
        valEl.style.fontFamily = "'SF Mono', 'Menlo', monospace";
      } else if (row.valClass === 'dim') {
        valEl.style.color = 'var(--info)';
        valEl.style.fontFamily = "'SF Mono', 'Menlo', monospace";
      }

      rowEl.appendChild(keyEl);
      rowEl.appendChild(valEl);
      section.appendChild(rowEl);
    }

    return section;
  }
}
