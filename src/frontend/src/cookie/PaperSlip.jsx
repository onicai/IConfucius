import { useMemo, useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { makeSlipHalfGeometry, remapSlipUVs } from './cookieGeometry.js';
import { makeQuoteTexture } from './textures.js';

const FOLD_H = -0.25; // bottom half pressed against the top (folded)
const OPEN_H = -Math.PI + 0.12; // unfolded with a residual crease
const SPLIT_T = 0.15;
const easeOutCubic = (k) => 1 - (1 - k) ** 3;

export default function PaperSlip({ stage, quote, reducedMotion, crackT0Ref, onRevealed }) {
  const slip = useRef();
  const hinge = useRef();
  const revealedSent = useRef(false);

  const geoTop = useMemo(() => remapSlipUVs(makeSlipHalfGeometry(), 0.5, 1), []);
  const geoBottom = useMemo(() => remapSlipUVs(makeSlipHalfGeometry(), 0.5, 0), []);
  const texture = useMemo(() => (quote ? makeQuoteTexture(quote) : null), [quote]);
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#fbf6ea',
        roughness: 0.9,
        side: THREE.DoubleSide,
        transparent: true,
      }),
    [],
  );
  material.map = texture;

  useEffect(() => {
    return () => {
      geoTop.dispose();
      geoBottom.dispose();
      material.dispose();
    };
  }, [geoTop, geoBottom, material]);
  useEffect(() => () => texture && texture.dispose(), [texture]);

  useFrame((state, dt) => {
    const g = slip.current;
    if (!g) return;
    const damp = THREE.MathUtils.damp;

    if (stage !== 'cracking' && stage !== 'revealed') {
      // hidden until the crack: the cookie tumbles independently, so a visible
      // folded slip would float detached from it
      g.visible = false;
      g.position.set(0, 0.15, 0.1);
      g.rotation.set(-0.35, 0, 0);
      g.scale.setScalar(0.7);
      hinge.current.rotation.x = FOLD_H;
      material.opacity = 1;
      revealedSent.current = false;
      return;
    }
    g.visible = true;

    const tc = crackT0Ref.current == null ? 0 : state.clock.elapsedTime - crackT0Ref.current;

    if (reducedMotion) {
      hinge.current.rotation.x = OPEN_H;
      g.position.set(0, 0.45, 1.9);
      g.rotation.set(0, 0, 0);
      g.scale.setScalar(1);
      g.quaternion.copy(state.camera.quaternion);
      if (!revealedSent.current && tc > 0.6) {
        revealedSent.current = true;
        onRevealed();
      }
    } else {
      // emerge + unfold: 0.5–1.4 s (let the halves-flying moment read first)
      const k = easeOutCubic(THREE.MathUtils.clamp((tc - 0.5) / 0.9, 0, 1));
      if (tc > SPLIT_T) {
        g.position.y = THREE.MathUtils.lerp(0.15, 0.45, k);
        g.position.z = THREE.MathUtils.lerp(0.1, 1.9, k);
        g.scale.setScalar(THREE.MathUtils.lerp(0.7, 1, k));
        hinge.current.rotation.x = THREE.MathUtils.lerp(FOLD_H, OPEN_H, k);
      }
      // face the camera: 1.1 s onward
      if (tc > 1.1) {
        const lambda = 5;
        g.quaternion.slerp(state.camera.quaternion, 1 - Math.exp(-lambda * dt));
      }
      if (!revealedSent.current && tc > 2.1) {
        revealedSent.current = true;
        onRevealed();
      }
    }

    // after reveal, hand off to the DOM card: fade the slip out
    if (stage === 'revealed') {
      material.opacity = damp(material.opacity, 0, 6, dt);
    }
  });

  return (
    <group ref={slip}>
      <mesh geometry={geoTop} material={material} />
      <group ref={hinge}>
        <mesh geometry={geoBottom} material={material} />
      </group>
    </group>
  );
}
