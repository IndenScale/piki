import type { PikiProject, PikiInstance, SceneObject } from '../types/index.ts';
import type { ISelectionService } from '../core/selection/SelectionService.ts';
import { inferTypeFromId, typeColor } from '../utils/index.ts';
import { createPanel } from './components/Panel.ts';
import { createBadge } from './components/Badge.ts';
import { createEmptyState } from './components/EmptyState.ts';

export class SceneTree {
  private selectionService: ISelectionService;
  private element: HTMLElement | null = null;
  private treeContainer: HTMLElement | null = null;
  private project: PikiProject | null = null;
  private panel: ReturnType<typeof createPanel> | null = null;

  constructor(selectionService: ISelectionService) {
    this.selectionService = selectionService;
    this.selectionService.onChange((obj) => {
      this.updateVisualSelection(obj);
    });
  }

  render(): HTMLElement {
    this.panel = createPanel({ title: '场景层级' });
    this.element = this.panel.root;
    this.element.style.borderRight = '1px solid var(--border-color)';

    this.treeContainer = this.panel.content;
    this.treeContainer.style.padding = '6px 0';

    this.renderEmpty();

    return this.element;
  }

  setProject(project: PikiProject): void {
    this.project = project;
    this.renderTree();
  }

  private updateVisualSelection(obj: SceneObject | null): void {
    if (!this.treeContainer) return;
    const selectedName = obj?.name ?? null;
    this.treeContainer.querySelectorAll('.tree-item').forEach((item) => {
      const el = item as HTMLElement;
      if (selectedName && el.dataset.name === selectedName) {
        el.classList.add('selected');
        el.style.background = 'rgba(88, 166, 255, 0.1)';
        el.style.borderLeftColor = 'var(--info)';
      } else {
        el.classList.remove('selected');
        el.style.background = 'transparent';
        el.style.borderLeftColor = 'transparent';
      }
    });
  }

  private renderEmpty(): void {
    if (!this.treeContainer) return;
    this.treeContainer.innerHTML = '';
    this.treeContainer.appendChild(
      createEmptyState({
        title: '暂无场景数据',
        subtitle: '打开项目后在此处查看层级',
      }),
    );
  }

  private renderTree(): void {
    if (!this.treeContainer || !this.project) return;
    this.treeContainer.innerHTML = '';

    for (const collection of this.project.collections) {
      // Collection group header
      const groupItem = document.createElement('div');
      groupItem.className = 'tree-group';
      groupItem.style.padding = '5px 14px';
      groupItem.style.display = 'flex';
      groupItem.style.alignItems = 'center';
      groupItem.style.gap = '8px';
      groupItem.style.fontSize = '12px';
      groupItem.style.fontWeight = '600';
      groupItem.style.color = 'var(--text-secondary)';
      groupItem.style.userSelect = 'none';
      groupItem.style.cursor = 'default';

      const groupIcon = document.createElement('span');
      groupIcon.style.width = '10px';
      groupIcon.style.height = '10px';
      groupIcon.style.borderRadius = '2px';
      groupIcon.style.flexShrink = '0';
      groupIcon.style.background = 'var(--text-muted)';
      groupIcon.style.opacity = '0.5';

      const groupLabel = document.createElement('span');
      groupLabel.textContent = collection.name;
      groupLabel.style.flex = '1';

      const countBadge = createBadge(String(collection.instances.length), 'collection');

      groupItem.appendChild(groupIcon);
      groupItem.appendChild(groupLabel);
      groupItem.appendChild(countBadge);
      this.treeContainer.appendChild(groupItem);

      // Instances
      for (const inst of collection.instances) {
        const item = document.createElement('div');
        item.className = 'tree-item';
        item.dataset.name = inst.id;
        item.style.padding = '5px 14px 5px 28px';
        item.style.cursor = 'pointer';
        item.style.fontSize = '12px';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.gap = '8px';
        item.style.transition = 'all 0.12s ease';
        item.style.whiteSpace = 'nowrap';
        item.style.overflow = 'hidden';
        item.style.textOverflow = 'ellipsis';
        item.style.borderLeft = '2px solid transparent';
        item.style.color = 'var(--text-primary)';

        const icon = document.createElement('span');
        icon.style.width = '10px';
        icon.style.height = '10px';
        icon.style.borderRadius = '2px';
        icon.style.flexShrink = '0';
        icon.style.display = 'inline-block';
        icon.style.background = typeColor(inferTypeFromId(inst.id));

        const label = document.createElement('span');
        label.textContent = inst.id;
        label.style.overflow = 'hidden';
        label.style.textOverflow = 'ellipsis';
        label.style.flex = '1';

        item.appendChild(icon);
        item.appendChild(label);

        item.addEventListener('mouseenter', () => {
          if (!item.classList.contains('selected')) {
            item.style.background = 'var(--bg-tertiary)';
          }
        });
        item.addEventListener('mouseleave', () => {
          if (!item.classList.contains('selected')) {
            item.style.background = 'transparent';
          }
        });
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          const sceneObj: SceneObject = {
            name: inst.id,
            displayName: (inst.raw.name as string) || null,
            type: inferTypeFromId(inst.id),
            depth: 1,
            parent: null,
            children: [],
            geometry: null,
          };
          this.selectionService.setSelected(sceneObj);
        });

        this.treeContainer.appendChild(item);
      }
    }
  }
}
