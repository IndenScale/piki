import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { SceneObject } from '../types/piki.ts';

export class Viewport {
  private onSelect: (obj: SceneObject | null) => void;
  private element: HTMLElement | null = null;
  private canvasContainer: HTMLElement | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private controls: OrbitControls | null = null;
  private raycaster: THREE.Raycaster | null = null;
  private mouse: THREE.Vector2 | null = null;
  private sceneGroup: THREE.Group | null = null;
  private threeMeshes: THREE.Mesh[] = [];
  private originalMaterials: Map<THREE.Mesh, THREE.Material> = new Map();
  private selectedMesh: THREE.Mesh | null = null;
  private wireframeMode = false;
  private sceneObjects: SceneObject[] = [];
  private animFrameId = 0;

  constructor(onSelect: (obj: SceneObject | null) => void) {
    this.onSelect = onSelect;
  }

  render(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'piki-viewport';
    el.style.flex = '1';
    el.style.position = 'relative';
    el.style.background = '#0a0a1a';
    el.style.overflow = 'hidden';

    // Toolbar
    const toolbar = document.createElement('div');
    toolbar.className = 'viewport-toolbar';
    toolbar.style.position = 'absolute';
    toolbar.style.top = '12px';
    toolbar.style.left = '12px';
    toolbar.style.display = 'flex';
    toolbar.style.gap = '6px';
    toolbar.style.zIndex = '10';

    const btnOrbit = this.createToolButton('🔄 旋转', true);
    const btnPan = this.createToolButton('✋ 平移', false);
    const btnZoom = this.createToolButton('🔍 缩放', false);
    const btnFit = this.createToolButton('⊡ 适配', false);
    const btnWireframe = this.createToolButton('▧ 线框', false);

    btnOrbit.addEventListener('click', () => {
      if (this.controls) {
        this.controls.mouseButtons = {
          LEFT: THREE.MOUSE.ROTATE,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.PAN,
        };
      }
      this.updateToolbar([btnOrbit, btnPan, btnZoom, btnFit, btnWireframe], btnOrbit);
    });
    btnPan.addEventListener('click', () => {
      if (this.controls) {
        this.controls.mouseButtons = {
          LEFT: THREE.MOUSE.PAN,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.ROTATE,
        };
      }
      this.updateToolbar([btnOrbit, btnPan, btnZoom, btnFit, btnWireframe], btnPan);
    });
    btnZoom.addEventListener('click', () => {
      if (this.controls) {
        this.controls.mouseButtons = {
          LEFT: THREE.MOUSE.DOLLY,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.PAN,
        };
      }
      this.updateToolbar([btnOrbit, btnPan, btnZoom, btnFit, btnWireframe], btnZoom);
    });
    btnFit.addEventListener('click', () => this.fitCamera());
    btnWireframe.addEventListener('click', () => {
      this.wireframeMode = !this.wireframeMode;
      for (const mesh of this.threeMeshes) {
        if (mesh.material instanceof THREE.MeshStandardMaterial) {
          mesh.material.wireframe = this.wireframeMode;
        }
      }
      btnWireframe.classList.toggle('active', this.wireframeMode);
    });

    toolbar.appendChild(btnOrbit);
    toolbar.appendChild(btnPan);
    toolbar.appendChild(btnZoom);
    toolbar.appendChild(btnFit);
    toolbar.appendChild(btnWireframe);
    el.appendChild(toolbar);

    // Canvas container
    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '100%';
    this.canvasContainer = container;
    el.appendChild(container);

    // Info overlay
    const info = document.createElement('div');
    info.className = 'viewport-info';
    info.textContent = '左键: 旋转 | 右键: 平移 | 滚轮: 缩放 | 点击: 选择';
    info.style.position = 'absolute';
    info.style.bottom = '12px';
    info.style.left = '12px';
    info.style.background = 'rgba(22, 33, 62, 0.9)';
    info.style.border = '1px solid #0f3460';
    info.style.borderRadius = '6px';
    info.style.padding = '8px 12px';
    info.style.fontSize = '11px';
    info.style.color = '#888';
    info.style.pointerEvents = 'none';
    info.style.zIndex = '10';
    el.appendChild(info);

    this.element = el;
    return el;
  }

  init(): void {
    if (!this.canvasContainer) return;

    const container = this.canvasContainer;
    const w = container.clientWidth || 800;
    const h = container.clientHeight || 600;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0a1a);

    // Camera
    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 1000);
    this.camera.position.set(3, 3, 3);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);

    // Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };

    // Lights
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.5);
    this.scene.add(hemiLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 10, 7);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    this.scene.add(dirLight);

    // Grid
    const grid = new THREE.GridHelper(10, 20, 0x333333, 0x1a1a2e);
    this.scene.add(grid);

    // Scene group for USD objects
    this.sceneGroup = new THREE.Group();
    this.scene.add(this.sceneGroup);

    // Raycaster
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    // Events
    this.renderer.domElement.addEventListener('click', this.onCanvasClick.bind(this));
    this.renderer.domElement.addEventListener('mousemove', this.onCanvasHover.bind(this));
    window.addEventListener('resize', this.onResize.bind(this));

    // Animation loop
    this.animate();
  }

  loadUsda(content: string): void {
    this.sceneObjects = this.parseUsda(content);
    this.buildScene(this.sceneObjects);
  }

  highlightObject(name: string): void {
    if (this.selectedMesh && this.originalMaterials.has(this.selectedMesh)) {
      this.selectedMesh.material = this.originalMaterials.get(this.selectedMesh)!;
    }
    const mesh = this.threeMeshes.find((m) => m.userData.object?.name === name);
    if (mesh) {
      this.selectedMesh = mesh;
      const highlightMat = (mesh.material as THREE.MeshStandardMaterial).clone();
      highlightMat.emissive = new THREE.Color(0x444444);
      mesh.material = highlightMat;

      // Focus camera
      const box = new THREE.Box3().setFromObject(mesh);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const distance = Math.max(size.x, size.y, size.z) * 3;
      if (this.controls && this.camera) {
        this.controls.target.copy(center);
        this.camera.position.set(center.x + distance, center.y + distance * 0.5, center.z + distance);
        this.controls.update();
      }
    }
  }

  private parseUsda(content: string): SceneObject[] {
    const objects: SceneObject[] = [];
    const lines = content.split('\n');
    let stack: SceneObject[] = [];
    let currentObj: SceneObject | null = null;
    let currentGeo: { type: string; transform: number[]; color: { r: number; g: number; b: number }; size: number } | null = null;
    let braceDepth = 0;

    for (const line of lines) {
      const trimmed = line.trim();
      const openBraces = (line.match(/\{/g) || []).length;
      const closeBraces = (line.match(/\}/g) || []).length;

      // def Xform "name"
      const xformMatch = trimmed.match(/def\s+Xform\s+"([^"]+)"\s*(?:\(([^)]*)\))?/);
      if (xformMatch) {
        const obj: SceneObject = {
          name: xformMatch[1],
          displayName: null,
          type: 'group',
          depth: braceDepth,
          parent: stack.length > 0 ? stack[stack.length - 1] : null,
          geometry: null,
          children: [],
        };

        if (xformMatch[2]) {
          const dnMatch = xformMatch[2].match(/displayName\s*=\s*"([^"]*)"/);
          if (dnMatch) obj.displayName = dnMatch[1];
        }

        if (obj.name.startsWith('RACK')) obj.type = 'rack';
        else if (obj.name.startsWith('SRV') || obj.name.startsWith('device')) obj.type = 'device';
        else if (obj.name.startsWith('PDU')) obj.type = 'pdu';
        else if (['devices', 'racks', 'pdus'].includes(obj.name)) obj.type = 'collection';

        if (stack.length > 0) {
          stack[stack.length - 1].children.push(obj);
        }

        objects.push(obj);
        currentObj = obj;
        stack.push(obj);
      }

      // def Cube "geometry"
      const cubeMatch = trimmed.match(/def\s+(Cube|Mesh)\s+"geometry"/);
      if (cubeMatch && currentObj) {
        currentGeo = {
          type: cubeMatch[1].toLowerCase(),
          transform: new THREE.Matrix4().toArray(),
          color: { r: 0.7, g: 0.7, b: 0.7 },
          size: 1,
        };
        currentObj.geometry = currentGeo;
      }

      // matrix4d xformOp:transform
      const matrixMatch = trimmed.match(/matrix4d\s+xformOp:transform\s*=\s*(\([^)]+\))/);
      if (matrixMatch && currentGeo) {
        const nums = matrixMatch[1].match(/-?\d+\.?\d*(?:e[+-]?\d+)?/gi)?.map(Number);
        if (nums && nums.length === 16) {
          currentGeo.transform = nums;
        }
      }

      // color3f[] primvars:displayColor
      const colorMatch = trimmed.match(/color3f\[\]\s+primvars:displayColor\s*=\s*\[(\([^)]+\))\]/);
      if (colorMatch && currentGeo) {
        const nums = colorMatch[1].match(/\d+\.?\d*/g)?.map(Number);
        if (nums && nums.length >= 3) {
          currentGeo.color = { r: nums[0], g: nums[1], b: nums[2] };
        }
      }

      // double size = N
      const sizeMatch = trimmed.match(/double\s+size\s*=\s*(\d+\.?\d*)/);
      if (sizeMatch && currentGeo) {
        currentGeo.size = parseFloat(sizeMatch[1]);
      }

      braceDepth += openBraces - closeBraces;

      if (closeBraces > 0 && stack.length > 0) {
        for (let b = 0; b < closeBraces && stack.length > 0; b++) {
          stack.pop();
        }
        currentObj = stack.length > 0 ? stack[stack.length - 1] : null;
        currentGeo = null;
      }
    }

    return objects;
  }

  private buildScene(objects: SceneObject[]): void {
    if (!this.sceneGroup) return;

    // Clear previous
    while (this.sceneGroup.children.length > 0) {
      this.sceneGroup.remove(this.sceneGroup.children[0]);
    }
    this.threeMeshes = [];
    this.originalMaterials.clear();

    const boxGeo = new THREE.BoxGeometry(1, 1, 1);

    for (const obj of objects) {
      if (!obj.geometry) continue;
      const geo = obj.geometry;

      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(geo.color.r, geo.color.g, geo.color.b),
        roughness: 0.6,
        metalness: 0.15,
      });

      const mesh = new THREE.Mesh(boxGeo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData = { object: obj };

      const m = new THREE.Matrix4();
      m.fromArray(geo.transform);
      mesh.applyMatrix4(m);

      // Edges outline
      const edges = new THREE.EdgesGeometry(boxGeo);
      const lineMat = new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.2 });
      const wireframe = new THREE.LineSegments(edges, lineMat);
      mesh.add(wireframe);

      this.sceneGroup.add(mesh);
      this.threeMeshes.push(mesh);
      this.originalMaterials.set(mesh, mat.clone());
    }

    this.fitCamera();
  }

  private fitCamera(): void {
    if (!this.camera || !this.controls || this.threeMeshes.length === 0) return;
    const box = new THREE.Box3();
    for (const m of this.threeMeshes) box.expandByObject(m);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const distance = maxDim * 2.5;

    this.controls.target.copy(center);
    this.camera.position.set(center.x + distance * 0.8, center.y + distance, center.z + distance);
    this.camera.lookAt(center);
    this.controls.update();
  }

  private onCanvasClick(event: MouseEvent): void {
    if (!this.raycaster || !this.mouse || !this.camera || !this.renderer) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.threeMeshes);

    if (intersects.length > 0) {
      const obj = intersects[0].object.userData.object as SceneObject;
      if (obj) this.onSelect(obj);
    } else {
      if (this.selectedMesh && this.originalMaterials.has(this.selectedMesh)) {
        this.selectedMesh.material = this.originalMaterials.get(this.selectedMesh)!;
      }
      this.selectedMesh = null;
      this.onSelect(null);
    }
  }

  private onCanvasHover(event: MouseEvent): void {
    if (!this.raycaster || !this.mouse || !this.camera || !this.renderer) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.threeMeshes);
    this.renderer.domElement.style.cursor = intersects.length > 0 ? 'pointer' : 'default';
  }

  private onResize(): void {
    if (!this.camera || !this.renderer || !this.canvasContainer) return;
    const w = this.canvasContainer.clientWidth || 800;
    const h = this.canvasContainer.clientHeight || 600;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  private animate(): void {
    this.animFrameId = requestAnimationFrame(this.animate.bind(this));
    if (this.controls) this.controls.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  private createToolButton(label: string, active: boolean): HTMLButtonElement {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.className = active ? 'toolbar-btn active' : 'toolbar-btn';
    btn.style.background = active ? '#e94560' : 'rgba(22, 33, 62, 0.9)';
    btn.style.border = '1px solid #0f3460';
    btn.style.color = '#e0e0e0';
    btn.style.padding = '6px 12px';
    btn.style.borderRadius = '6px';
    btn.style.fontSize = '12px';
    btn.style.cursor = 'pointer';
    btn.style.transition = 'all 0.15s';
    btn.addEventListener('mouseenter', () => {
      if (!btn.classList.contains('active')) {
        btn.style.background = '#1a2744';
        btn.style.borderColor = '#e94560';
      }
    });
    btn.addEventListener('mouseleave', () => {
      if (!btn.classList.contains('active')) {
        btn.style.background = 'rgba(22, 33, 62, 0.9)';
        btn.style.borderColor = '#0f3460';
      }
    });
    return btn;
  }

  private updateToolbar(buttons: HTMLButtonElement[], active: HTMLButtonElement): void {
    for (const btn of buttons) {
      btn.classList.remove('active');
      btn.style.background = 'rgba(22, 33, 62, 0.9)';
      btn.style.borderColor = '#0f3460';
    }
    active.classList.add('active');
    active.style.background = '#e94560';
    active.style.borderColor = '#e94560';
  }
}
