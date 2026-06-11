/**
 * ThreeRenderer — Three.js 渲染器封装
 *
 * 职责：封装 Three.js 的所有细节，提供声明式的场景渲染接口。
 * Core Layer（SceneService）通过此接口操作 3D 场景，不直接依赖 three 包。
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { SceneObject } from '../../types/index.ts';

export interface IThreeRenderer {
  /** 将渲染器挂载到指定 DOM 容器 */
  mount(container: HTMLElement): void;

  /** 加载场景对象列表 */
  loadScene(objects: SceneObject[]): void;

  /** 高亮指定名称的对象 */
  highlightObject(name: string): void;

  /** 清除高亮 */
  clearHighlight(): void;

  /** 注册对象选择回调 */
  onSelect(callback: (name: string | null) => void): void;

  /** 设置相机控制模式 */
  setCameraMode(mode: 'orbit' | 'pan' | 'zoom'): void;

  /** 将相机适配到场景包围盒 */
  fitView(): void;

  /** 切换线框模式 */
  setWireframe(enabled: boolean): void;

  /** 销毁渲染器，释放资源 */
  destroy(): void;
}

export class ThreeRenderer implements IThreeRenderer {
  private container: HTMLElement | null = null;
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
  private animFrameId = 0;
  private onSelectCallback: ((name: string | null) => void) | null = null;

  mount(container: HTMLElement): void {
    this.container = container;
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
    this.renderer.domElement.addEventListener('click', this._onCanvasClick.bind(this));
    this.renderer.domElement.addEventListener('mousemove', this._onCanvasHover.bind(this));
    window.addEventListener('resize', this._onResize.bind(this));

    // Animation loop
    this._animate();
  }

  loadScene(objects: SceneObject[]): void {
    if (!this.sceneGroup) return;

    // Clear previous
    while (this.sceneGroup.children.length > 0) {
      this.sceneGroup.remove(this.sceneGroup.children[0]);
    }
    this.threeMeshes = [];
    this.originalMaterials.clear();
    this.selectedMesh = null;

    const boxGeo = new THREE.BoxGeometry(1, 1, 1);

    for (const obj of objects) {
      if (!obj.geometry) continue;
      const geo = obj.geometry;

      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(geo.color.r, geo.color.g, geo.color.b),
        roughness: 0.6,
        metalness: 0.15,
        wireframe: this.wireframeMode,
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

    this.fitView();
  }

  highlightObject(name: string): void {
    this._restoreSelectedMaterial();

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

  clearHighlight(): void {
    this._restoreSelectedMaterial();
    this.selectedMesh = null;
  }

  onSelect(callback: (name: string | null) => void): void {
    this.onSelectCallback = callback;
  }

  setCameraMode(mode: 'orbit' | 'pan' | 'zoom'): void {
    if (!this.controls) return;
    switch (mode) {
      case 'orbit':
        this.controls.mouseButtons = {
          LEFT: THREE.MOUSE.ROTATE,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.PAN,
        };
        break;
      case 'pan':
        this.controls.mouseButtons = {
          LEFT: THREE.MOUSE.PAN,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.ROTATE,
        };
        break;
      case 'zoom':
        this.controls.mouseButtons = {
          LEFT: THREE.MOUSE.DOLLY,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.PAN,
        };
        break;
    }
  }

  fitView(): void {
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

  setWireframe(enabled: boolean): void {
    this.wireframeMode = enabled;
    for (const mesh of this.threeMeshes) {
      if (mesh.material instanceof THREE.MeshStandardMaterial) {
        mesh.material.wireframe = enabled;
      }
    }
  }

  destroy(): void {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
    }
    if (this.renderer) {
      this.renderer.domElement.removeEventListener('click', this._onCanvasClick.bind(this));
      this.renderer.domElement.removeEventListener('mousemove', this._onCanvasHover.bind(this));
      window.removeEventListener('resize', this._onResize.bind(this));
      this.renderer.dispose();
      if (this.container && this.renderer.domElement.parentNode === this.container) {
        this.container.removeChild(this.renderer.domElement);
      }
    }
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.container = null;
  }

  // ─── Private ───

  private _restoreSelectedMaterial(): void {
    if (this.selectedMesh && this.originalMaterials.has(this.selectedMesh)) {
      this.selectedMesh.material = this.originalMaterials.get(this.selectedMesh)!;
    }
  }

  private _onCanvasClick(event: MouseEvent): void {
    if (!this.raycaster || !this.mouse || !this.camera || !this.renderer) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.threeMeshes);

    if (intersects.length > 0) {
      const obj = intersects[0].object.userData.object as SceneObject;
      if (obj && this.onSelectCallback) {
        this.onSelectCallback(obj.name);
      }
    } else {
      this.clearHighlight();
      if (this.onSelectCallback) {
        this.onSelectCallback(null);
      }
    }
  }

  private _onCanvasHover(event: MouseEvent): void {
    if (!this.raycaster || !this.mouse || !this.camera || !this.renderer) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.threeMeshes);
    this.renderer.domElement.style.cursor = intersects.length > 0 ? 'pointer' : 'default';
  }

  private _onResize(): void {
    if (!this.camera || !this.renderer || !this.container) return;
    const w = this.container.clientWidth || 800;
    const h = this.container.clientHeight || 600;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  private _animate(): void {
    this.animFrameId = requestAnimationFrame(this._animate.bind(this));
    if (this.controls) this.controls.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }
}
