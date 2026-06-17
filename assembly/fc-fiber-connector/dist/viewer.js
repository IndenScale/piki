/**
 * ADL Assembly Viewer — 通用浏览器渲染器。
 *
 * 加载同目录下的 scene.json，按其中 entity / control 定义渲染 Three.js 场景
 * 并生成交互面板。
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ── State ──
let scene, camera, renderer, controls;
let sceneData = null;
const entityObjects = new Map();   // id -> { group, baseTransform, mesh, material }
const controlState = new Map();    // control id -> current value

// ── Init ──
async function init() {
  const container = document.getElementById('canvas');

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);

  camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 1, 100000);
  camera.position.set(600, 400, 800);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.shadowMap.enabled = true;
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  scene.add(new THREE.AmbientLight(0x404060, 1.5));
  const sun = new THREE.DirectionalLight(0xffffff, 2);
  sun.position.set(500, 800, 500);
  sun.castShadow = true;
  scene.add(sun);

  // Grid helper (1m)
  const grid = new THREE.GridHelper(10000, 20, 0x444466, 0x2a2a3e);
  grid.position.y = -500;
  scene.add(grid);

  window.addEventListener('resize', onResize);

  try {
    sceneData = await loadSceneData();
    buildScene(sceneData);
    buildPanel(sceneData);
    fitCamera();
    document.getElementById('loading').style.display = 'none';
  } catch (err) {
    document.getElementById('loading').textContent = '加载失败: ' + err.message;
    console.error(err);
  }

  animate();
}

async function loadSceneData() {
  const res = await fetch('scene.json');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function onResize() {
  const container = document.getElementById('canvas');
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

// ── Scene Building ──
function buildScene(data) {
  document.getElementById('title').textContent = data.name || '装配体演示';
  document.getElementById('desc').textContent = data.description || '';

  for (const entity of data.entities) {
    createEntity(entity);
  }

  // 碰撞高亮
  if (data.collisions) {
    for (const [idA, idB] of data.collisions) {
      const objA = entityObjects.get(idA);
      const objB = entityObjects.get(idB);
      if (objA) objA.material.emissive.setHex(0xaa0000);
      if (objB) objB.material.emissive.setHex(0xaa0000);
    }
  }
}

function createEntity(entity) {
  const group = new THREE.Group();
  group.name = entity.id;

  const tf = entity.transform;
  group.position.set(
    tf.translation[0] / 1000,
    tf.translation[1] / 1000,
    tf.translation[2] / 1000
  );
  group.rotation.set(
    THREE.MathUtils.degToRad(tf.rotation[0]),
    THREE.MathUtils.degToRad(tf.rotation[1]),
    THREE.MathUtils.degToRad(tf.rotation[2])
  );
  group.scale.set(tf.scale[0], tf.scale[1], tf.scale[2]);

  const mesh = buildMesh(entity.geometry, entity.material);
  if (mesh) group.add(mesh);

  // 接口小点
  if (entity.interfaces) {
    for (const iface of entity.interfaces) {
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.005, 8, 8),
        new THREE.MeshBasicMaterial({ color: 0xffaa00 })
      );
      dot.position.set(
        iface.local_transform.translation[0] / 1000,
        iface.local_transform.translation[1] / 1000,
        iface.local_transform.translation[2] / 1000
      );
      group.add(dot);
    }
  }

  scene.add(group);

  const material = mesh ? mesh.material : null;
  entityObjects.set(entity.id, {
    group,
    baseTransform: cloneTransform(tf),
    mesh,
    material,
    entity,
  });
}

function buildMesh(geometry, materialDef) {
  if (!geometry) return null;
  const mat = new THREE.MeshStandardMaterial({
    color: materialDef.color || '#888888',
    transparent: (materialDef.opacity || 1) < 1,
    opacity: materialDef.opacity ?? 1,
    roughness: materialDef.roughness ?? 0.5,
    metalness: materialDef.metalness ?? 0,
    wireframe: materialDef.wireframe || false,
  });

  let mesh = null;
  if (geometry.type === 'box' && geometry.size) {
    const sx = geometry.size.x / 1000;
    const sy = geometry.size.y / 1000;
    const sz = geometry.size.z / 1000;
    const geo = new THREE.BoxGeometry(sx, sy, sz);
    mesh = new THREE.Mesh(geo, mat);
  } else if (geometry.type === 'cylinder' && geometry.radius && geometry.height) {
    const r = geometry.radius / 1000;
    const h = geometry.height / 1000;
    const geo = new THREE.CylinderGeometry(r, r, h, 32);
    mesh = new THREE.Mesh(geo, mat);
  } else if (geometry.type === 'sphere' && geometry.radius) {
    const r = geometry.radius / 1000;
    const geo = new THREE.SphereGeometry(r, 32, 16);
    mesh = new THREE.Mesh(geo, mat);
  } else if (geometry.type === 'capsule' && geometry.radius && geometry.height) {
    const r = geometry.radius / 1000;
    const h = geometry.height / 1000;
    const geo = new THREE.CapsuleGeometry(r, h - 2 * r, 4, 16);
    mesh = new THREE.Mesh(geo, mat);
  }

  if (mesh && geometry.transform) {
    mesh.position.set(
      geometry.transform.translation[0] / 1000,
      geometry.transform.translation[1] / 1000,
      geometry.transform.translation[2] / 1000
    );
    mesh.rotation.set(
      THREE.MathUtils.degToRad(geometry.transform.rotation[0]),
      THREE.MathUtils.degToRad(geometry.transform.rotation[1]),
      THREE.MathUtils.degToRad(geometry.transform.rotation[2])
    );
  }

  return mesh;
}

function cloneTransform(tf) {
  return {
    translation: [...tf.translation],
    rotation: [...tf.rotation],
    scale: [...tf.scale],
  };
}

function applyTransform(obj, tf) {
  obj.group.position.set(
    tf.translation[0] / 1000,
    tf.translation[1] / 1000,
    tf.translation[2] / 1000
  );
  obj.group.rotation.set(
    THREE.MathUtils.degToRad(tf.rotation[0]),
    THREE.MathUtils.degToRad(tf.rotation[1]),
    THREE.MathUtils.degToRad(tf.rotation[2])
  );
}

// ── Panel Building ──
function buildPanel(data) {
  const panel = document.getElementById('panel');

  // 诊断信息
  if (data.diagnostics && data.diagnostics.length > 0) {
    const diagDiv = document.createElement('div');
    diagDiv.className = 'diagnostics';
    diagDiv.innerHTML = '<h3>诊断</h3>';
    for (const d of data.diagnostics) {
      const el = document.createElement('div');
      el.className = `diagnostic ${d.severity || 'info'}`;
      el.textContent = `[${d.code}] ${d.message}`;
      diagDiv.appendChild(el);
    }
    panel.appendChild(diagDiv);
  }

  // 控件
  for (const ctrl of data.controls || []) {
    controlState.set(ctrl.id, ctrl.default);

    if (ctrl.type === 'slider') {
      buildSlider(panel, ctrl);
    } else if (ctrl.type === 'button') {
      buildButton(panel, ctrl);
    }
  }
}

function buildSlider(panel, ctrl) {
  const group = document.createElement('div');
  group.className = 'group';

  const label = document.createElement('label');
  label.textContent = ctrl.label || ctrl.param;
  group.appendChild(label);

  const value = document.createElement('div');
  value.className = 'value';
  value.textContent = `${ctrl.default.toFixed(1)} ${ctrl.param}`;
  group.appendChild(value);

  const input = document.createElement('input');
  input.type = 'range';
  input.min = ctrl.min;
  input.max = ctrl.max;
  input.step = ctrl.step ?? 1;
  input.value = ctrl.default;
  group.appendChild(input);

  input.addEventListener('input', () => {
    const v = parseFloat(input.value);
    value.textContent = `${v.toFixed(1)} ${ctrl.param}`;
    controlState.set(ctrl.id, v);
    updateControl(ctrl);
  });

  panel.appendChild(group);
}

function buildButton(panel, ctrl) {
  const group = document.createElement('div');
  group.className = 'group';

  const label = document.createElement('label');
  label.textContent = ctrl.label || ctrl.param;
  group.appendChild(label);

  const btns = document.createElement('div');
  btns.className = 'preset';

  for (const state of ctrl.states) {
    const btn = document.createElement('button');
    btn.className = 'state-btn' + (state === ctrl.current_state ? ' active' : '');
    btn.textContent = state;
    btn.addEventListener('click', () => {
      for (const b of btns.children) b.classList.remove('active');
      btn.classList.add('active');
      controlState.set(ctrl.id, state);
      updateControl(ctrl);
    });
    btns.appendChild(btn);
  }

  group.appendChild(btns);
  panel.appendChild(group);
}

// ── Control Application ──
function updateControl(ctrl) {
  const target = ctrl.target; // e.g. "SWITCH-01/cage-1→SFP28-01/tail"
  const parsed = parseControlTarget(target);
  if (!parsed) return;

  const parentObj = entityObjects.get(parsed.parentId);
  const childObj = entityObjects.get(parsed.childId);
  if (!parentObj || !childObj) return;

  const parentIface = parentObj.entity.interfaces.find(i => i.id === parsed.parentIface);
  const childIface = childObj.entity.interfaces.find(i => i.id === parsed.childIface);
  if (!parentIface || !childIface) return;

  // 目前支持 slot / face-on-face 的轻量 delta 更新
  if (ctrl.param === 't') {
    updateSlot(childObj, parentObj, parentIface, childIface, controlState.get(ctrl.id), ctrl.default);
  } else if (['u', 'v', 'theta_deg', 'distance'].includes(ctrl.param)) {
    updateFaceOnFace(childObj, parentObj, parentIface, childIface, ctrl);
  }
}

function parseControlTarget(target) {
  // format: "parentId/parentIface→childId/childIface"
  const arrowIdx = target.indexOf('→');
  if (arrowIdx < 0) return null;
  const left = target.slice(0, arrowIdx);
  const right = target.slice(arrowIdx + 1);
  const [parentId, parentIface] = left.split('/');
  const [childId, childIface] = right.split('/');
  return { parentId, parentIface, childId, childIface };
}

function updateSlot(childObj, parentObj, parentIface, childIface, newT, defaultT) {
  const slotDir = parentIface.mating_params?.slot_dir || [0, 0, -1];
  const dt = newT - defaultT;

  const base = childObj.baseTransform;
  const newTf = cloneTransform(base);

  // delta 沿 slot_dir，单位 mm
  newTf.translation[0] += slotDir[0] * dt;
  newTf.translation[1] += slotDir[1] * dt;
  newTf.translation[2] += slotDir[2] * dt;

  applyTransform(childObj, newTf);
}

function updateFaceOnFace(childObj, parentObj, parentIface, childIface, ctrl) {
  // 简化：distance 沿 Y 轴；u/v 在 XZ 平面
  const base = childObj.baseTransform;
  const newTf = cloneTransform(base);

  const u = controlState.get(ctrl.id.replace(ctrl.param, 'u')) ?? 0;
  const v = controlState.get(ctrl.id.replace(ctrl.param, 'v')) ?? 0;
  const dist = controlState.get(ctrl.id.replace(ctrl.param, 'distance')) ?? 0;
  const theta = controlState.get(ctrl.id.replace(ctrl.param, 'theta_deg')) ?? 0;

  // 这里只做最简单的距离偏移（Y 轴）
  if (ctrl.param === 'distance') {
    newTf.translation[1] = base.translation[1] + (controlState.get(ctrl.id) - ctrl.default);
  }

  applyTransform(childObj, newTf);
}

function fitCamera() {
  if (entityObjects.size === 0) return;
  const box = new THREE.Box3();
  for (const obj of entityObjects.values()) {
    box.expandByObject(obj.group);
  }
  const center = new THREE.Vector3();
  box.getCenter(center);
  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z);
  const dist = maxDim * 1.5;
  camera.position.set(center.x + dist, center.y + dist * 0.8, center.z + dist);
  controls.target.copy(center);
  controls.update();
}

init();
