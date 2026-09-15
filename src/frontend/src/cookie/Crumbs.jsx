import { useMemo, useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const N = 80;
const SPLIT_T = 0.15;
const LIFE = 1.2;

export default function Crumbs({ stage, reducedMotion, crackT0Ref }) {
  const mesh = useRef();
  const data = useRef(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const geometry = useMemo(() => new THREE.TetrahedronGeometry(0.035), []);
  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ color: '#d9a85c', roughness: 0.8 }),
    [],
  );
  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  useFrame((state, delta) => {
    const m = mesh.current;
    if (!m) return;
    if (stage !== 'cracking' && stage !== 'revealed') {
      m.count = 0;
      data.current = null;
      return;
    }
    if (reducedMotion) {
      m.count = 0;
      return;
    }
    const tc = crackT0Ref.current == null ? 0 : state.clock.elapsedTime - crackT0Ref.current;
    if (tc < SPLIT_T) return;
    if (tc - SPLIT_T > LIFE) {
      m.count = 0;
      return;
    }

    if (!data.current) {
      data.current = Array.from({ length: N }, () => {
        const side = Math.random() < 0.5 ? -1 : 1;
        return {
          pos: new THREE.Vector3(
            (Math.random() - 0.5) * 0.1,
            0.1 + Math.random() * 0.5,
            (Math.random() - 0.5) * 0.4,
          ),
          vel: new THREE.Vector3(
            side * (0.6 + Math.random() * 2.4),
            0.5 + Math.random() * 1.5,
            (Math.random() - 0.5) * 1.5,
          ),
          rot: new THREE.Euler(
            Math.random() * Math.PI,
            Math.random() * Math.PI,
            Math.random() * Math.PI,
          ),
          spin: (Math.random() - 0.5) * 8,
          scale: 0.6 + Math.random() * 0.8,
        };
      });
      m.count = N;
    }

    const dt = Math.min(delta, 1 / 30);
    const fade = 1 - (tc - SPLIT_T) / LIFE;
    data.current.forEach((c, i) => {
      c.vel.y -= 4.5 * dt;
      c.pos.addScaledVector(c.vel, dt);
      c.rot.x += c.spin * dt;
      c.rot.z += c.spin * 0.7 * dt;
      dummy.position.copy(c.pos);
      dummy.rotation.copy(c.rot);
      dummy.scale.setScalar(Math.max(0.0001, c.scale * fade));
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[geometry, material, N]} count={0} frustumCulled={false} />
  );
}
