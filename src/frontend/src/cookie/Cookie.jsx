import { useMemo, useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { makeHalfCookieGeometry } from './cookieGeometry.js';
import { makeNoiseBumpTexture } from './textures.js';

const REST_ROT = [0.6, -0.6, 0.1]; // resting on the fold belly, cheek to camera
const SPLIT_T = 0.15; // crack timeline: anticipation ends, halves fly

// wrap an angle to its nearest equivalent of target so damp takes the short way
function nearest(current, target) {
  return current - 2 * Math.PI * Math.round((current - target) / (2 * Math.PI));
}

export default function Cookie({ stage, reducedMotion, crackT0Ref, onSettled, onCrack }) {
  const root = useRef();
  const left = useRef();
  const right = useRef();
  const wrapped = useRef(false);
  const halves = useRef(null); // physics state, seeded at crack time
  const prevStage = useRef(null);
  const tumbleT0 = useRef(0);

  const geoL = useMemo(() => makeHalfCookieGeometry(-1), []);
  const geoR = useMemo(() => makeHalfCookieGeometry(1), []);
  const materials = useMemo(() => {
    const noise = makeNoiseBumpTexture();
    return [
      new THREE.MeshPhysicalMaterial({
        color: '#e6c298',
        roughness: 0.62,
        metalness: 0,
        clearcoat: 0.15,
        clearcoatRoughness: 0.6,
        bumpMap: noise,
        bumpScale: 0.4,
      }),
      new THREE.MeshStandardMaterial({
        color: '#f2ddb8',
        roughness: 1.0,
        bumpMap: noise,
        bumpScale: 1.4,
      }),
    ];
  }, []);

  useEffect(() => {
    return () => {
      geoL.dispose();
      geoR.dispose();
      materials.forEach((m) => {
        if (m.bumpMap) m.bumpMap.dispose();
        m.dispose();
      });
    };
  }, [geoL, geoR, materials]);

  useEffect(() => {
    if (stage !== 'settling') wrapped.current = false;
  }, [stage]);

  useFrame((state, dt) => {
    const g = root.current;
    if (!g) return;
    const t = state.clock.elapsedTime;
    const damp = THREE.MathUtils.damp;
    if (prevStage.current !== stage) {
      if (stage === 'tumbling') tumbleT0.current = t;
      prevStage.current = stage;
    }

    if (stage === 'resting') {
      // idle pose: table rest with a slow breathing sway
      g.rotation.x = damp(g.rotation.x, REST_ROT[0], 4, dt);
      g.rotation.z = damp(g.rotation.z, REST_ROT[2], 4, dt);
      g.rotation.y = damp(g.rotation.y, REST_ROT[1] + (reducedMotion ? 0 : 0.12 * Math.sin(t * 0.5)), 4, dt);
      g.position.y = damp(g.position.y, reducedMotion ? 0 : 0.02 * Math.sin(t * 0.8), 4, dt);
      g.scale.setScalar(damp(g.scale.x, 1, 8, dt));
    } else if (stage === 'tumbling') {
      if (reducedMotion) {
        g.rotation.set(0.35, g.rotation.y + 0.1 * dt, 0);
      } else {
        // damp toward the moving tumble targets so entry from rest is smooth;
        // tumble-local clock so the spin starts from zero, not absolute time
        const tt = t - tumbleT0.current;
        g.rotation.x = damp(g.rotation.x, 0.55 * Math.sin(tt * 1.7) + 0.25 * Math.sin(tt * 2.9 + 1.3), 6, dt);
        g.rotation.y = damp(g.rotation.y, REST_ROT[1] + tt * 0.9 + 0.4 * Math.sin(tt * 1.3 + 0.7), 6, dt);
        g.rotation.z = damp(g.rotation.z, 0.3 * Math.sin(tt * 0.8 + 2.1), 6, dt);
        g.position.y = damp(g.position.y, 0.08 * Math.sin(tt * 1.1), 6, dt);
      }
    } else if (stage === 'settling') {
      if (!wrapped.current) {
        g.rotation.x = nearest(g.rotation.x, REST_ROT[0]);
        g.rotation.y = nearest(g.rotation.y, REST_ROT[1]);
        g.rotation.z = nearest(g.rotation.z, REST_ROT[2]);
        wrapped.current = true;
      }
      g.rotation.x = damp(g.rotation.x, REST_ROT[0], 4, dt);
      g.rotation.y = damp(g.rotation.y, REST_ROT[1], 4, dt);
      g.rotation.z = damp(g.rotation.z, REST_ROT[2], 4, dt);
      g.position.y = damp(g.position.y, 0, 4, dt);
      const done =
        Math.abs(g.rotation.x - REST_ROT[0]) < 0.01 &&
        Math.abs(g.rotation.y - REST_ROT[1]) < 0.01 &&
        Math.abs(g.rotation.z - REST_ROT[2]) < 0.01;
      if (done || reducedMotion) onSettled();
    } else if (stage === 'invite') {
      const s = 1 + (reducedMotion ? 0 : 0.03 * Math.sin(t * 2.4));
      g.scale.setScalar(damp(g.scale.x, s, 8, dt));
      if (!reducedMotion) g.rotation.z = 0.02 * Math.sin(t * 1.6);
    } else if (stage === 'cracking' || stage === 'revealed') {
      const tc = crackT0Ref.current == null ? 0 : t - crackT0Ref.current;
      if (reducedMotion) {
        // gentle cross-fade apart, no physics
        left.current.position.x = damp(left.current.position.x, -1.35, 3, dt);
        right.current.position.x = damp(right.current.position.x, 1.35, 3, dt);
        left.current.position.y = damp(left.current.position.y, -0.35, 3, dt);
        right.current.position.y = damp(right.current.position.y, -0.35, 3, dt);
        return;
      }
      if (tc < SPLIT_T) {
        g.scale.x = damp(g.scale.x, 0.96, 20, dt); // anticipation squeeze
        return;
      }
      if (!halves.current) {
        g.scale.setScalar(1);
        halves.current = [left, right].map((ref, i) => ({
          ref,
          vel: new THREE.Vector3(
            (i === 0 ? -1 : 1) * 2.2,
            0.6 + Math.random() * 0.4,
            0.2 * (Math.random() - 0.5),
          ),
          angVel: new THREE.Vector3(
            (Math.random() - 0.5) * 3,
            (Math.random() - 0.5) * 3,
            (Math.random() - 0.5) * 3,
          ),
          rest: new THREE.Vector3(i === 0 ? -1.35 : 1.35, -0.35, 0),
          restRot: new THREE.Euler(1.1, 0, i === 0 ? 0.6 : -0.6),
        }));
      }
      for (const h of halves.current) {
        const m = h.ref.current;
        if (!m) continue;
        if (tc < 1.0) {
          m.position.addScaledVector(h.vel, dt);
          h.vel.multiplyScalar(Math.exp(-3 * dt));
          h.vel.y -= 3 * dt;
          m.rotation.x += h.angVel.x * dt;
          m.rotation.y += h.angVel.y * dt;
          m.rotation.z += h.angVel.z * dt;
        } else {
          m.position.x = damp(m.position.x, h.rest.x, 4, dt);
          m.position.y = damp(m.position.y, h.rest.y, 4, dt);
          m.position.z = damp(m.position.z, h.rest.z, 4, dt);
          m.rotation.x = damp(nearest(m.rotation.x, h.restRot.x), h.restRot.x, 4, dt);
          m.rotation.y = damp(nearest(m.rotation.y, h.restRot.y), h.restRot.y, 4, dt);
          m.rotation.z = damp(nearest(m.rotation.z, h.restRot.z), h.restRot.z, 4, dt);
        }
      }
    }
  });

  const clickable = stage === 'invite';
  const hover = (on) => {
    if (!clickable) return;
    document.body.style.cursor = on ? 'pointer' : '';
  };

  return (
    <group
      ref={root}
      onClick={clickable ? onCrack : undefined}
      onPointerOver={() => hover(true)}
      onPointerOut={() => hover(false)}
    >
      <mesh ref={left} geometry={geoL} material={materials} />
      <mesh ref={right} geometry={geoR} material={materials} />
    </group>
  );
}
