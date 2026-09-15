import { useRef, useEffect } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { ContactShadows } from '@react-three/drei';
import Cookie from './Cookie.jsx';
import PaperSlip from './PaperSlip.jsx';
import Crumbs from './Crumbs.jsx';

export default function CookieScene({ stage, quote, reducedMotion, onSettled, onCrack, onRevealed }) {
  const { camera } = useThree();
  const crackT0Ref = useRef(null);
  const clockRef = useRef(0);

  useEffect(() => {
    camera.position.set(0, 0.9, 4.6);
    camera.lookAt(0, 0.15, 0);
  }, [camera]);

  useFrame((state) => {
    clockRef.current = state.clock.elapsedTime;
  });

  useEffect(() => {
    if (stage === 'cracking') crackT0Ref.current = clockRef.current;
    if (stage === 'tumbling') crackT0Ref.current = null;
  }, [stage]);

  return (
    <>
      <hemisphereLight args={['#fff5e0', '#8a7357', 0.7]} />
      <directionalLight position={[2.5, 4, 2.5]} intensity={2.2} color="#fff1d6" />
      <directionalLight position={[-3, 1.5, -2.5]} intensity={1.1} color="#bcd0ff" />
      <ContactShadows
        position={[0, -0.85, 0]}
        opacity={0.45}
        scale={5}
        blur={2.4}
        far={2}
        resolution={256}
        frames={Infinity}
      />
      <Cookie
        stage={stage}
        reducedMotion={reducedMotion}
        crackT0Ref={crackT0Ref}
        onSettled={onSettled}
        onCrack={onCrack}
      />
      <PaperSlip
        stage={stage}
        quote={quote}
        reducedMotion={reducedMotion}
        crackT0Ref={crackT0Ref}
        onRevealed={onRevealed}
      />
      <Crumbs stage={stage} reducedMotion={reducedMotion} crackT0Ref={crackT0Ref} />
    </>
  );
}
