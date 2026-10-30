/* Street Lighting — 3D street view (three.js).
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 *
 * Engine axes: x along the road, y to the left, z up.  three.js uses y up,
 * so a point (x, y, z) is drawn at (x, z, -y).
 *
 * Views:  day        — materials and sunlight, to see the geometry
 *         night      — the road surface shows the calculated luminance
 *                      (or illuminance on footways) as perceived brightness
 *         false      — calculated values in a colour scale with a legend
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { colour, clamp } from './util.js';

const V = (x, y, z) => new THREE.Vector3(x, z, -y);

export class Street3D {
  constructor(host) {
    this.host = host;
    host.__street3d = this;   // hook for the browser tests (renderer.info, frame count)
    this.frames = 0;
    this.mode = 'night';
    this.quantity = 'L';
    this.scale = 'classic';
    this.showCones = false;
    // no preserveDrawingBuffer: snapshot() renders and reads the canvas in the same task, which is
    // enough, and keeping the buffer costs fill-rate on every frame
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    const cv = this.renderer.domElement;
    cv.setAttribute('role', 'img');
    cv.setAttribute('aria-label', '3D view of the street. Drag to orbit, scroll to zoom, arrow keys to pan; the camera buttons above give fixed views.');
    cv.setAttribute('aria-describedby', 'hint3d');
    cv.tabIndex = 0;
    host.appendChild(cv);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
    this.camera.position.set(-30, 25, 30);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.495;
    this.controls.addEventListener('change', () => this.invalidate());
    this.controls.listenToKeyEvents(cv);          // arrow keys pan the view when the canvas has focus
    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.sun = new THREE.DirectionalLight(0xffffff, 2.2);
    this.sun.position.set(-60, 120, 40);
    this.amb = new THREE.HemisphereLight(0xcfe3ff, 0x4a4030, 1.1);
    this.scene.add(this.sun, this.amb);
    this.data = null;
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.resize();
    // render on demand: the street is static, so a frame is drawn only after something changed
    // (camera, data, size) or while the orbit damping is still settling
    this.dirty = true;
    this.renderer.setAnimationLoop(() => {
      if (this.host.offsetParent === null || document.hidden) return;   // hidden pane: draw nothing
      const moving = this.controls.update();
      if (moving || this.dirty) {
        this.dirty = false;
        this.renderer.render(this.scene, this.camera);
        this.frames++;
      }
    });
    // a pane that becomes visible again needs one fresh frame
    new IntersectionObserver(() => this.invalidate()).observe(host);
  }

  invalidate() { this.dirty = true; }

  resize() {
    const w = this.host.clientWidth || 600, h = this.host.clientHeight || 400;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.invalidate();
  }

  clear() {
    for (const c of [...this.root.children]) {
      this.root.remove(c);
      c.traverse(o => {
        if (o.isInstancedMesh) o.dispose();          // frees the instance buffers
        if (o.geometry) o.geometry.dispose();
        if (o.material) [].concat(o.material).forEach(m => { if (m.map) m.map.dispose(); m.dispose(); });
      });
    }
  }

  setMode(mode, quantity, scale) {
    this.invalidate();
    this.mode = mode || this.mode;
    if (quantity) this.quantity = quantity;
    if (scale) this.scale = scale;
    if (this.data) this.build(this.data, false);
  }

  /* data: {surfaces:[{xyz:Float32Array(n*3), nx, ny, E:[], L:[]|null, kind}], poles:[{base:[x,y,z], head:[x,y,z], H, nu}],
            trees:[{x,y,zc,r,rv}], marks:[[x,y,z],...][], vmax:{E,L}, cct, extent:{x0,x1,y0,y1} } */
  build(data, resetCamera = true) {
    this.data = data;
    this.clear();
    const night = this.mode !== 'day';
    this.scene.background = new THREE.Color(night ? 0x0b1220 : 0xbfd3e6);
    this.scene.fog = night ? new THREE.Fog(0x0b1220, 120, 600) : new THREE.Fog(0xbfd3e6, 300, 1500);
    this.sun.intensity = night ? 0.05 : 2.2;
    this.amb.intensity = night ? 0.18 : 1.1;
    const ex = data.extent;
    // ground plane
    const gw = (ex.x1 - ex.x0) + 400, gh = (ex.y1 - ex.y0) + 400;
    const g = new THREE.Mesh(new THREE.PlaneGeometry(gw, gh),
      new THREE.MeshLambertMaterial({ color: night ? 0x0f1716 : 0x7d8f62 }));
    g.rotation.x = -Math.PI / 2;
    g.position.set((ex.x0 + ex.x1) / 2, (data.zmin ?? 0) - 0.05, -(ex.y0 + ex.y1) / 2);
    this.root.add(g);
    // surfaces
    const tint = cctTint(data.cct || 3000);
    const vmaxE = data.vmax.E || 1, vmaxL = data.vmax.L || 1;
    for (const s of data.surfaces) {
      const geo = new THREE.BufferGeometry();
      const n = s.ns * s.ny;
      const pos = new Float32Array(n * 3);
      const lift = { footway: 0.15, cycleway: 0.12, median: 0.15, verge: 0.12 }[s.kind] || 0;
      for (let k = 0; k < n; k++) {
        const x = s.xyz[3 * k], y = s.xyz[3 * k + 1], z = s.xyz[3 * k + 2] + lift;
        pos[3 * k] = x; pos[3 * k + 1] = z; pos[3 * k + 2] = -y;
      }
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      const idx = [];
      for (let i = 0; i < s.ns - 1; i++) {
        for (let j = 0; j < s.ny - 1; j++) {
          const a = i * s.ny + j, b = (i + 1) * s.ny + j, c = (i + 1) * s.ny + j + 1, d = i * s.ny + j + 1;
          idx.push(a, b, c, a, c, d);
        }
      }
      geo.setIndex(idx);
      geo.computeVertexNormals();
      let mat;
      if (this.mode === 'day') {
        const col = { carriageway: 0x4a4f57, footway: 0xa9a49a, cycleway: 0x8c5a4a, median: 0x6f8a55, verge: 0x6f8a55,
          parking: 0x5d6168 }[s.kind] || 0x777777;
        mat = new THREE.MeshLambertMaterial({ color: col });
      } else {
        const cols = new Float32Array(n * 3);
        const useL = this.quantity === 'L' && s.L;
        const vals = useL ? s.L : s.E;
        const vmax = useL ? vmaxL : vmaxE;
        for (let k = 0; k < n; k++) {
          let c;
          if (this.mode === 'night') {
            // perceived brightness: luminance (or E * rho / pi for pavements) through a soft tone curve
            // a fixed exposure keeps designs comparable: about 2 cd/m2 reads as a bright street
            const lum = useL ? vals[k] : vals[k] * (s.kind === 'carriageway' ? 0.07 : 0.2) / Math.PI;
            const b = Math.pow(1 - Math.exp(-lum / 1.6), 1.25);
            const base = s.kind === 'carriageway' ? 0.022 : 0.03;
            c = [clamp(base + b * tint[0], 0, 1), clamp(base + b * tint[1], 0, 1), clamp(base * 1.5 + b * tint[2], 0, 1)];
          } else {
            const cc = colour(vals[k] / vmax, this.scale);
            c = [cc[0] / 255, cc[1] / 255, cc[2] / 255];
          }
          // the values above are display (sRGB) values; vertex colours are linear
          c = c.map(v => Math.pow(v, 2.2));
          cols[3 * k] = c[0]; cols[3 * k + 1] = c[1]; cols[3 * k + 2] = c[2];
        }
        geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));
        mat = new THREE.MeshBasicMaterial({ vertexColors: true });
      }
      this.root.add(new THREE.Mesh(geo, mat));
      // kerb faces for raised strips (simple vertical skirts along both edges)
      if (lift > 0) this.root.add(kerb(s, lift, night));
    }
    // Repeated objects are drawn as instanced meshes: one draw call per kind of part instead of one
    // per object (a 600 m route went from about 240 draw calls to about 25).
    const dummy = new THREE.Object3D();
    const inst = (geo, mat, list, place) => {
      if (!list.length) return null;
      const m = new THREE.InstancedMesh(geo, mat, list.length);
      list.forEach((it, i) => { dummy.position.set(0, 0, 0); dummy.rotation.set(0, 0, 0); dummy.quaternion.identity(); dummy.scale.set(1, 1, 1);
        place(it, dummy); dummy.updateMatrix(); m.setMatrixAt(i, dummy.matrix); });
      m.instanceMatrix.needsUpdate = true;
      m.computeBoundingSphere();
      this.root.add(m);
      return m;
    };
    // road markings (dashes): a unit box scaled to each dash
    const dashes = [];
    for (const line of data.marks || []) for (let i = 0; i + 1 < line.length; i += 2) dashes.push([line[i], line[i + 1]]);
    inst(new THREE.BoxGeometry(1, 0.02, 0.12), new THREE.MeshBasicMaterial({ color: night ? 0x50555c : 0xf2f2ee }), dashes, ([a, b], o) => {
      o.position.copy(V((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2 + 0.01));
      o.rotation.y = Math.atan2(b[1] - a[1], b[0] - a[0]);
      o.scale.x = Math.hypot(b[0] - a[0], b[1] - a[1]);
    });
    // poles, arms and luminaire heads
    const poleMat = new THREE.MeshLambertMaterial({ color: night ? 0x2a3038 : 0x8d949c });
    const headMat = new THREE.MeshLambertMaterial({ color: 0x3b4148 });
    const poles = data.poles || [];
    inst(new THREE.CylinderGeometry(0.06, 0.1, 1, 10), poleMat, poles, (p, o) => {
      const H = p.head[2] - p.base[2];
      o.position.copy(V(p.base[0], p.base[1], p.base[2] + H / 2));
      o.scale.y = H;
    });
    const up = new THREE.Vector3(0, 1, 0);
    const arms = poles.filter(p => Math.hypot(p.head[0] - p.base[0], p.head[1] - p.base[1]) > 0.05);
    inst(new THREE.CylinderGeometry(0.035, 0.035, 1, 8), poleMat, arms, (p, o) => {
      const len = Math.hypot(p.head[0] - p.base[0], p.head[1] - p.base[1]);
      o.position.copy(V((p.base[0] + p.head[0]) / 2, (p.base[1] + p.head[1]) / 2, p.head[2] + 0.05));
      o.quaternion.setFromUnitVectors(up, V(p.head[0] - p.base[0], p.head[1] - p.base[1], 0).normalize());
      o.scale.y = len;
    });
    const placeHead = (dy) => (p, o) => {
      o.position.copy(V(p.head[0], p.head[1], p.head[2]));
      o.position.y += dy;
      o.rotation.y = (p.nu || 0) * Math.PI / 180;
    };
    inst(new THREE.BoxGeometry(0.75, 0.12, 0.32), headMat, poles, placeHead(0));
    if (night) {
      const lit = new THREE.Color(tint[0], tint[1], tint[2]);
      const lensGeo = new THREE.PlaneGeometry(0.6, 0.24).rotateX(Math.PI / 2);
      inst(lensGeo, new THREE.MeshBasicMaterial({ color: lit, side: THREE.DoubleSide }), poles, placeHead(-0.065));
      // halos: one point cloud (a single draw call) with an additive glow texture in place of a sprite per pole
      const hp = new Float32Array(poles.length * 3);
      poles.forEach((p, i) => { const v = V(p.head[0], p.head[1], p.head[2] - 0.2); hp[3 * i] = v.x; hp[3 * i + 1] = v.y; hp[3 * i + 2] = v.z; });
      const hg = new THREE.BufferGeometry();
      hg.setAttribute('position', new THREE.BufferAttribute(hp, 3));
      this.root.add(new THREE.Points(hg, new THREE.PointsMaterial({ map: haloTexture(tint), size: 6.9, sizeAttenuation: true,   // 3.2 m glow: point size is in half-viewport units (x 1/tan 25°)
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.85 })));
      if (this.showCones) {
        const coneGeo = new THREE.ConeGeometry(1.1, 1, 32, 1, true).translate(0, -0.5, 0);
        inst(coneGeo, new THREE.MeshBasicMaterial({ color: lit, transparent: true, opacity: 0.06, depthWrite: false,
          side: THREE.DoubleSide, blending: THREE.AdditiveBlending }), poles, (p, o) => {
          const h = Math.max(p.head[2] - p.base[2] - 0.2, 1);
          o.position.copy(V(p.head[0], p.head[1], p.head[2] - 0.1));
          o.scale.set(h, h, h);
        });
      }
    }
    // trees: trunks and crowns
    const trees = data.trees || [];
    const trunkH = t => Math.max(t.zc - t.rv - (t.z0 ?? 0), 0.5) + t.rv * 0.4;
    inst(new THREE.CylinderGeometry(0.12, 0.18, 1, 8), new THREE.MeshLambertMaterial({ color: night ? 0x1d1712 : 0x6b4a2f }), trees, (t, o) => {
      const h = trunkH(t);
      o.position.copy(V(t.x, t.y, (t.z0 ?? 0) + h / 2));
      o.scale.y = h;
    });
    inst(new THREE.IcosahedronGeometry(1, 2), new THREE.MeshLambertMaterial({ color: night ? 0x0f2416 : 0x3f7a3a }), trees, (t, o) => {
      o.position.copy(V(t.x, t.y, t.zc));
      o.scale.set(t.r, t.rv, t.r);
    });
    // labels (dimensions)
    for (const lb of data.labels || []) {
      const sp = textSprite(lb.text, night);
      sp.position.copy(V(lb.p[0], lb.p[1], lb.p[2]));
      this.root.add(sp);
    }
    for (const dl of data.dims || []) {
      const geo = new THREE.BufferGeometry().setFromPoints(dl.map(q => V(q[0], q[1], q[2])));
      this.root.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: night ? 0xf2c230 : 0x1a3550 })));
    }
    if (resetCamera) this.view('bird');
    this.invalidate();
  }

  view(kind) {
    const d = this.data;
    if (!d) return;
    const ex = d.extent;
    const cx = (ex.x0 + ex.x1) / 2, cy = (ex.y0 + ex.y1) / 2;
    const span = Math.max(ex.x1 - ex.x0, ex.y1 - ex.y0, 20);
    const z0 = d.zmin ?? 0;
    if (kind === 'driver' && d.driver) {
      const o = d.driver;
      this.camera.position.copy(V(o.eye[0], o.eye[1], o.eye[2]));
      this.controls.target.copy(V(o.look[0], o.look[1], o.look[2]));
      this.camera.fov = 45;
    } else if (kind === 'side') {
      this.camera.position.copy(V(cx, ex.y0 - span * 0.45, z0 + 6));
      this.controls.target.copy(V(cx, cy, z0 + 3));
      this.camera.fov = 50;
    } else if (kind === 'top') {
      this.camera.position.copy(V(cx, cy, z0 + span * 0.9));
      this.controls.target.copy(V(cx + 0.01, cy, z0));
      this.camera.fov = 50;
    } else if (kind === 'whole' || !d.start) {
      this.camera.position.copy(V(ex.x0 - span * 0.15, ex.y0 - span * 0.35, z0 + span * 0.32));
      this.controls.target.copy(V(cx, cy, z0));
      this.camera.fov = 50;
    } else {
      // long route: an oblique view of the first stretch
      const o = d.start;
      this.camera.position.copy(V(o.eye[0], o.eye[1], o.eye[2]));
      this.controls.target.copy(V(o.look[0], o.look[1], o.look[2]));
      this.camera.fov = 50;
    }
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  snapshot() { this.renderer.render(this.scene, this.camera); return this.renderer.domElement.toDataURL('image/png'); }

  dispose() {
    this.renderer.setAnimationLoop(null);
    this.clear();
    this.controls.dispose();
    this.ro.disconnect();
    this.renderer.dispose();
  }
}

function kerb(s, lift, night) {
  const g = new THREE.Group();
  const mat = new THREE.MeshLambertMaterial({ color: night ? 0x1a1f26 : 0x9a968c, side: THREE.DoubleSide });
  for (const j of [0, s.ny - 1]) {
    const pos = [];
    for (let i = 0; i < s.ns; i++) {
      const k = i * s.ny + j;
      const x = s.xyz[3 * k], y = s.xyz[3 * k + 1], z = s.xyz[3 * k + 2];
      pos.push(x, z, -y, x, z + lift, -y);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
    const idx = [];
    for (let i = 0; i < s.ns - 1; i++) { const a = 2 * i; idx.push(a, a + 2, a + 3, a, a + 3, a + 1); }
    geo.setIndex(idx);
    geo.computeVertexNormals();
    g.add(new THREE.Mesh(geo, mat));
  }
  return g;
}

function cctTint(K) {
  // approximate white point of the light source (normalised RGB)
  if (K <= 2100) return [1.0, 0.72, 0.38];
  if (K <= 2800) return [1.0, 0.82, 0.58];
  if (K <= 3300) return [1.0, 0.88, 0.70];
  if (K <= 4300) return [1.0, 0.95, 0.86];
  return [0.93, 0.96, 1.0];
}

function haloTexture(t) {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  const col = (a) => `rgba(${Math.round(255 * t[0])},${Math.round(255 * t[1])},${Math.round(255 * t[2])},${a})`;
  g.addColorStop(0, col(1)); g.addColorStop(0.15, col(0.6)); g.addColorStop(0.5, col(0.12)); g.addColorStop(1, col(0));
  x.fillStyle = g;
  x.fillRect(0, 0, 64, 64);
  const tx = new THREE.CanvasTexture(c);
  tx.colorSpace = THREE.SRGBColorSpace;   // a colour texture: without this the glow renders washed out
  return tx;
}

function textSprite(text, night) {
  const c = document.createElement('canvas');
  const x = c.getContext('2d');
  x.font = '600 34px Barlow, system-ui, sans-serif';
  const w = Math.ceil(x.measureText(text).width) + 24;
  c.width = w; c.height = 50;
  x.font = '600 34px Barlow, system-ui, sans-serif';
  x.fillStyle = night ? 'rgba(15,22,36,0.85)' : 'rgba(255,255,255,0.9)';
  x.fillRect(0, 0, w, 50);
  x.fillStyle = night ? '#f2c230' : '#1a3550';
  x.fillText(text, 12, 36);
  const tx = new THREE.CanvasTexture(c);
  tx.colorSpace = THREE.SRGBColorSpace;
  tx.anisotropy = 4;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tx, depthTest: false, transparent: true }));
  sp.scale.set(w / 50 * 0.9, 0.9, 1);
  sp.renderOrder = 10;
  return sp;
}
