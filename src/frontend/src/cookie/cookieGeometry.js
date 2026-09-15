import * as THREE from 'three';

export const R = 1.0; // dough disc radius
const T = 0.075; // dough thickness
const RHO1 = 0.62; // taco-fold bend radius
const RHO2 = 1.3; // corner-curl bend radius (~90° total horn bend)
const NR = 14;
const NT = 28;
const NZ = 2;
const JAG = 0.02; // crack-face jitter

// deterministic hash noise (organic dough, jagged crack)
function hash(x, y, z) {
  const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453;
  return s - Math.floor(s);
}

// Map a point of the FLAT thick disc into the folded cookie shape.
// Flat coords: x along the fold line, y across it, z thickness (±T/2).
export function deform(v) {
  // taco fold: wrap the (y,z) plane onto a cylinder of radius RHO1 (axis = X);
  // a point at thickness offset z sits at radius RHO1 - z (exact thick bend)
  const a1 = v.y / RHO1;
  const y1 = (RHO1 - v.z) * Math.sin(a1);
  const z1 = RHO1 - (RHO1 - v.z) * Math.cos(a1);
  // corner curl: bend the fold line the opposite way so the horns at x = ±R
  // dip and come toward each other
  const a2 = v.x / RHO2;
  const x2 = (RHO2 + z1) * Math.sin(a2);
  const z2 = (RHO2 + z1) * Math.cos(a2) - RHO2;
  // a whisper of dough noise so the silhouette is not mathematically perfect
  const n = (hash(v.x * 5.1, v.y * 5.1, 0) - 0.5) * 0.012;
  v.set(x2, y1 + n, z2 + n);
}

// One half of the cookie, split at the crack plane x = 0.
// side: +1 → right half (θ ∈ [-π/2, π/2]), -1 → left half (θ ∈ [π/2, 3π/2]).
// Material groups: 0 = crust (top/bottom/rim), 1 = interior (crack face).
export function makeHalfCookieGeometry(side) {
  const positions = [];
  const uvs = [];
  const indices = [];
  const v = new THREE.Vector3();

  // Emit an (nu+1)×(nv+1) grid; point(u, w, v) fills v with FLAT coords.
  function emit(nu, nv, point, flip) {
    const base = positions.length / 3;
    const start = indices.length;
    for (let i = 0; i <= nu; i++) {
      for (let j = 0; j <= nv; j++) {
        point(i / nu, j / nv, v);
        uvs.push(0.5 + v.x / (2 * R), 0.5 + v.y / (2 * R)); // planar pre-deform UVs
        deform(v);
        positions.push(v.x, v.y, v.z);
      }
    }
    for (let i = 0; i < nu; i++) {
      for (let j = 0; j < nv; j++) {
        const a = base + i * (nv + 1) + j;
        const b = a + nv + 1;
        if (flip) indices.push(a, a + 1, b, a + 1, b + 1, b);
        else indices.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
    return start;
  }

  const th = (u) => (side > 0 ? -Math.PI / 2 : Math.PI / 2) + side * Math.PI * u;

  // crust: top face, bottom face (flipped winding), outer rim strip
  emit(NR, NT, (u, w, p) => p.set(R * u * Math.cos(th(w)), R * u * Math.sin(th(w)), T / 2), false);
  emit(NR, NT, (u, w, p) => p.set(R * u * Math.cos(th(w)), R * u * Math.sin(th(w)), -T / 2), true);
  emit(NT, NZ, (u, w, p) => p.set(R * Math.cos(th(u)), R * Math.sin(th(u)), -T / 2 + T * w), false);

  // crack face at x = 0: midline vertices recess inward for a rough break;
  // boundary rows stay flush so the closed cookie shows only a hairline seam
  const crackStart = emit(
    2 * NR,
    NZ,
    (u, w, p) => {
      const y = -R + 2 * R * u;
      let x = 0;
      if (w > 0 && w < 1) x = -side * hash(y * 13.7, w, 3.1) * JAG;
      p.set(x, y, -T / 2 + T * w);
    },
    side > 0,
  );

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geo.setIndex(indices);
  geo.addGroup(0, crackStart, 0); // crust
  geo.addGroup(crackStart, indices.length - crackStart, 1); // interior
  geo.computeVertexNormals();
  return geo;
}

// One half of the paper slip: a gently curled plane with its hinge edge at y = 0.
export function makeSlipHalfGeometry(w = 1.6, h = 0.5, curl = 0.06) {
  const geo = new THREE.PlaneGeometry(w, h, 24, 4);
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    pos.setZ(i, curl * (1 - Math.cos((x / w) * Math.PI * 2)) * 0.5);
    pos.setY(i, pos.getY(i) + h / 2); // hinge edge at y = 0
  }
  geo.computeVertexNormals();
  return geo;
}

// Remap the v range of a slip-half geometry's UVs (top half samples [0.5, 1],
// bottom half [0, 0.5] of the shared quote texture).
export function remapSlipUVs(geo, v0, v1) {
  const uv = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++) {
    uv.setY(i, v0 + uv.getY(i) * (v1 - v0));
  }
  uv.needsUpdate = true;
  return geo;
}
