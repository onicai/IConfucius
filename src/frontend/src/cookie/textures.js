import * as THREE from 'three';

// 128×128 value-noise bump texture for the dough surface (fully procedural).
export function makeNoiseBumpTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(128, 128);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = (118 + Math.random() * 60) | 0;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  // soften into blotches by compositing itself at lower scales
  ctx.globalAlpha = 0.5;
  ctx.drawImage(c, 0, 0, 128, 128, 0, 0, 256, 256);
  ctx.drawImage(c, 0, 0, 64, 64, 0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(3, 3);
  return tex;
}

// CJK ranges: split these characters into standalone wrap units.
const CJK_SPLIT = /([⺀-鿿　-〿＀-￯])/;

function wrapUnits(quote) {
  const units = [];
  for (const token of quote.split(/(\s+)/)) {
    if (!token) continue;
    if (/^\s+$/.test(token)) {
      units.push(' ');
    } else {
      for (const part of token.split(CJK_SPLIT)) {
        if (part) units.push(part);
      }
    }
  }
  return units;
}

// Render the quote onto a 1024×640 canvas (slip aspect 1.6:1). Canvas 2D does
// per-glyph system-font fallback, so CJK and Devanagari render without any
// bundled font files.
export function makeQuoteTexture(quote) {
  const W = 1024;
  const H = 640;
  const PAD_X = 70;
  const PAD_Y = 60;
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const ctx = c.getContext('2d');

  // paper background with a subtle edge vignette and a thin jade rule
  ctx.fillStyle = '#fbf6ea';
  ctx.fillRect(0, 0, W, H);
  const grad = ctx.createRadialGradient(W / 2, H / 2, H / 3, W / 2, H / 2, W / 1.4);
  grad.addColorStop(0, 'rgba(43,38,34,0)');
  grad.addColorStop(1, 'rgba(43,38,34,0.08)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#3d7a5c';
  ctx.lineWidth = 3;
  ctx.strokeRect(26, 26, W - 52, H - 52);

  const units = wrapUnits(quote);
  const maxWidth = W - 2 * PAD_X;
  const maxHeight = H - 2 * PAD_Y;
  let lines = [];
  let size = 46;
  for (; size >= 26; size -= 4) {
    ctx.font = `${size}px Georgia, 'Times New Roman', serif`;
    lines = [];
    let line = '';
    for (const unit of units) {
      const candidate = line + unit;
      if (line !== '' && ctx.measureText(candidate).width > maxWidth) {
        lines.push(line.trimEnd());
        line = unit === ' ' ? '' : unit;
      } else {
        line = candidate;
      }
    }
    if (line.trimEnd()) lines.push(line.trimEnd());
    if (lines.length * size * 1.4 <= maxHeight) break;
  }

  ctx.font = `${size}px Georgia, 'Times New Roman', serif`;
  ctx.fillStyle = '#2b2622';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const lineHeight = size * 1.4;
  const y0 = H / 2 - ((lines.length - 1) * lineHeight) / 2;
  lines.forEach((l, i) => ctx.fillText(l, W / 2, y0 + i * lineHeight));

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}
