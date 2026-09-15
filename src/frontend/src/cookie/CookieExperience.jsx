import { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import CookieScene from './CookieScene.jsx';

const reducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Sub-states: tumbling -> settling -> invite -> cracking -> revealed
export default function CookieExperience({ phase, quote, crackLabel, readyLabel, onRevealed }) {
  const [stage, setStage] = useState('tumbling');

  useEffect(() => {
    if (phase === 'loading') setStage('tumbling');
    else if (phase === 'done') setStage((s) => (s === 'tumbling' ? 'settling' : s));
  }, [phase]);

  const crack = () => {
    document.body.style.cursor = '';
    setStage((s) => (s === 'invite' ? 'cracking' : s));
  };

  return (
    <div className="cookie-stage">
      <Canvas
        dpr={[1, 2]}
        gl={{ alpha: true, antialias: true }}
        camera={{ fov: 35, position: [0, 0.9, 4.6] }}
        frameloop={stage === 'revealed' ? 'demand' : 'always'}
      >
        <CookieScene
          stage={stage}
          quote={quote}
          reducedMotion={reducedMotion}
          onSettled={() => setStage((s) => (s === 'settling' ? 'invite' : s))}
          onCrack={crack}
          onRevealed={() => {
            setStage('revealed');
            onRevealed();
          }}
        />
      </Canvas>
      {stage === 'invite' && (
        <>
          <p className="cookie-ready">{readyLabel}</p>
          <button type="button" className="crack-btn" aria-label={crackLabel} onClick={crack}>
            {crackLabel}
          </button>
        </>
      )}
    </div>
  );
}
