import type { PikiProject, PikiInstance, SceneObject } from '../types/piki.ts';

export class SceneTree {
  private onSelect: (obj: SceneObject | null) => void;
  private element: HTMLElement | null = null;
  private treeContainer: HTMLElement | null = null;
  private project: PikiProject | null = null;
  private selectedName: string | null = null;

  constructor(onSelect: (obj: SceneObject | null) => void) {
    this.onSelect = onSelect;
  }

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-scene-tree';
    this.applyStyles(el);

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
    icon.textContent = 'P';
    icon.style.width = '20px';
    icon.style.height = '20px';
    icon.style.background = '#e94560';
    icon.style.borderRadius = '4px';
    icon.style.display = 'flex';
    icon.style.alignItems = 'center';
    icon.style.justifyContent = 'center';
    icon.style.fontSize = '12px';
    icon.style.fontWeight = 'bold';
    icon.style.color = 'white';

    const title = document.createElement('span');
    title.textContent = '场景层级';

    header.appendChild(icon);
    header.appendChild(title);
    el.appendChild(header);

    // Tree container
    const tree = document.createElement('div');
    tree.className = 'tree-content';
    tree.style.flex = '1';
    tree.style.overflowY = 'auto';
    tree.style.padding = '8px 0';
    this.treeContainer = tree;
    el.appendChild(tree);

    // Empty state
    this.renderEmpty();

    this.element = el;
    return el;
  }

  setProject(project: PikiProject): void {
    this.project = project;
    this.renderTree();
  }

  selectObject(obj: SceneObject | null): void {
    this.selectedName = obj?.name ?? null;
    // Update visual selection
    if (this.treeContainer) {
      this.treeContainer.querySelectorAll('.tree-item').forEach((item) => {
        const el = item as HTMLElement;
        if (obj && el.dataset.name === obj.name) {
          el.classList.add('selected');
        } else {
          el.classList.remove('selected');
        }
      });
    }
  }

  private renderEmpty(): void {
    if (!this.treeContainer) return;
    this.treeContainer.innerHTML = '';
    const empty = document.createElement('div');
    empty.className = 'no-selection';
    empty.textContent = '点击顶部"打开项目"按钮加载工程';
    empty.style.textAlign = 'center';
    empty.style.color = '#666';
    empty.style.padding = '40px 20px';
    empty.style.fontSize = '13px';
    this.treeContainer.appendChild(empty);
  }

  private renderTree(): void {
    if (!this.treeContainer || !this.project) return;
    this.treeContainer.innerHTML = '';

    for (const collection of this.project.collections) {
      // Collection group
      const groupItem = document.createElement('div');
      groupItem.className = 'tree-item';
      groupItem.style.padding = '6px 16px';
      groupItem.style.cursor = 'pointer';
      groupItem.style.fontSize = '13px';
      groupItem.style.display = 'flex';
      groupItem.style.alignItems = 'center';
      groupItem.style.gap = '6px';
      groupItem.style.transition = 'background 0.15s';
      groupItem.style.whiteSpace = 'nowrap';
      groupItem.style.overflow = 'hidden';
      groupItem.style.textOverflow = 'ellipsis';
      groupItem.style.fontWeight = '600';
      groupItem.style.color = '#888';

      const groupIcon = document.createElement('span');
      groupIcon.className = 'icon group';
      groupIcon.style.width = '14px';
      groupIcon.style.height = '14px';
      groupIcon.style.borderRadius = '2px';
      groupIcon.style.flexShrink = '0';
      groupIcon.style.background = '#6c757d';
      groupIcon.style.display = 'inline-block';

      groupItem.appendChild(groupIcon);
      groupItem.appendChild(document.createTextNode(`${collection.name} (${collection.instances.length})`));
      this.treeContainer.appendChild(groupItem);

      // Instances
      for (const inst of collection.instances) {
        const item = document.createElement('div');
        item.className = 'tree-item';
        item.dataset.name = inst.id;
        item.style.padding = '6px 16px 6px 32px';
        item.style.cursor = 'pointer';
        item.style.fontSize = '13px';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.gap = '6px';
        item.style.transition = 'background 0.15s';
        item.style.whiteSpace = 'nowrap';
        item.style.overflow = 'hidden';
        item.style.textOverflow = 'ellipsis';
        if (this.selectedName === inst.id) {
          item.classList.add('selected');
        }

        const icon = document.createElement('span');
        icon.className = `icon ${this.getTypeIcon(inst)}`;
        icon.style.width = '14px';
        icon.style.height = '14px';
        icon.style.borderRadius = '2px';
        icon.style.flexShrink = '0';
        icon.style.display = 'inline-block';
        icon.style.background = this.getTypeColor(inst);

        const label = document.createElement('span');
        label.textContent = inst.id;
        label.style.overflow = 'hidden';
        label.style.textOverflow = 'ellipsis';

        item.appendChild(icon);
        item.appendChild(label);

        item.addEventListener('mouseenter', () => {
          if (!item.classList.contains('selected')) {
            item.style.background = '#1a2744';
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
            type: this.getInstanceType(inst),
            depth: 1,
            parent: null,
            children: [],
            geometry: null,
          };
          this.onSelect(sceneObj);
        });

        this.treeContainer.appendChild(item);
      }
    }
  }

  private getTypeIcon(inst: PikiInstance): string {
    const id = inst.id.toLowerCase();
    if (id.startsWith('rack')) return 'rack';
    if (id.startsWith('pdu')) return 'pdu';
    if (id.startsWith('srv') || id.startsWith('device')) return 'device';
    return 'group';
  }

  private getTypeColor(inst: PikiInstance): string {
    const id = inst.id.toLowerCase();
    if (id.startsWith('rack')) return '#4a90d9';
    if (id.startsWith('pdu')) return '#f0ad4e';
    if (id.startsWith('srv') || id.startsWith('device')) return '#5cb85c';
    return '#6c757d';
  }

  private getInstanceType(inst: PikiInstance): SceneObject['type'] {
    const id = inst.id.toLowerCase();
    if (id.startsWith('rack')) return 'rack';
    if (id.startsWith('pdu')) return 'pdu';
    if (id.startsWith('srv') || id.startsWith('device')) return 'device';
    return 'group';
  }

  private applyStyles(el: HTMLElement): void {
    el.style.display = 'flex';
    el.style.flexDirection = 'column';
    el.style.background = '#16213e';
    el.style.borderRight = '1px solid #0f3460';
    el.style.overflow = 'hidden';
  }
}
