import { useEffect, useRef, useState } from 'react';

import { colors, font } from '@/lib/theme';

const OUT = 1024; // côté de la photo envoyée (px) : nette sur tous les écrans, ~150 à 300 Ko en JPEG

/**
 * Recadrage libre dans un cercle : glisser pour déplacer, pincer (ou molette) pour zoomer de très loin à très près,
 * pivoter par quarts de tour. Le résultat est une image carrée de 1024 px, prête à être envoyée.
 */
export function PhotoCropper({ src, onCancel, onDone }: { src: string; onCancel: () => void; onDone: (uri: string) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, scale: 1, rot: 0 });
  const [fit, setFit] = useState({ min: 0.1, max: 10 });
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const size = Math.min(typeof window === 'undefined' ? 320 : window.innerWidth - 48, 360);

  useEffect(() => {
    const image = new Image();
    image.src = src;
    image.decode().then(() => {
      // Couvre le cercle au départ ; on peut dézoomer jusqu'à voir la photo entière en petit, ou zoomer ×8.
      const cover = size / Math.min(image.naturalWidth, image.naturalHeight);
      const contain = size / Math.max(image.naturalWidth, image.naturalHeight);
      setFit({ min: contain * 0.4, max: cover * 8 });
      setView({ x: 0, y: 0, scale: cover, rot: 0 });
      setImg(image);
    }).catch(() => setError('Ce format de photo ne peut pas être lu sur cet appareil (par exemple HEIC hors iPhone). Choisis une image JPEG, PNG ou WebP.'));
  }, [src, size]);

  useEffect(() => {
    const c = canvas.current;
    if (!c || !img) return;
    const ratio = window.devicePixelRatio || 1;
    c.width = size * ratio;
    c.height = size * ratio;
    draw(c.getContext('2d')!, img, view, size, ratio, true);
  }, [img, view, size]);

  const clamp = (s: number) => Math.min(fit.max, Math.max(fit.min, s));
  const zoomBy = (factor: number) => setView((v) => ({ ...v, scale: clamp(v.scale * factor) }));

  function down(e: React.PointerEvent) {
    (e.target as Element).setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
  }
  function move(e: React.PointerEvent) {
    const all = pointers.current;
    const prev = all.get(e.pointerId);
    if (!prev) return;
    const next = { x: e.clientX, y: e.clientY };
    if (all.size === 1) {
      setView((v) => ({ ...v, x: v.x + next.x - prev.x, y: v.y + next.y - prev.y }));
    } else if (all.size === 2) {
      const other = [...all.entries()].find(([id]) => id !== e.pointerId)![1];
      const before = Math.hypot(prev.x - other.x, prev.y - other.y);
      const after = Math.hypot(next.x - other.x, next.y - other.y);
      if (before > 0) setView((v) => ({ ...v, scale: clamp(v.scale * (after / before)), x: v.x + (next.x - prev.x) / 2, y: v.y + (next.y - prev.y) / 2 }));
    }
    all.set(e.pointerId, next);
  }
  const up = (e: React.PointerEvent) => pointers.current.delete(e.pointerId);

  function done() {
    if (!img) return;
    const out = document.createElement('canvas');
    out.width = OUT;
    out.height = OUT;
    draw(out.getContext('2d')!, img, view, size, OUT / size, false);
    out.toBlob((blob) => {
      if (blob) onDone(URL.createObjectURL(blob));
      else setError('La photo ne peut pas être préparée. Réessaie avec une autre image.');
    }, 'image/jpeg', 0.85);
  }

  const button = (label: string, onClick: () => void, primary = false, aria?: string) => (
    <button type="button" onClick={onClick} aria-label={aria ?? label} disabled={!img && primary}
      style={{ minHeight: 44, padding: '0 16px', borderRadius: 12, border: primary ? 0 : `1px solid ${colors.line}`, background: primary ? colors.accent : 'transparent',
        color: primary ? colors.onAccent : colors.text, font: 'inherit', fontWeight: 700, cursor: 'pointer', opacity: !img && primary ? 0.5 : 1 }}>{label}</button>
  );

  return (
    <div role="dialog" aria-modal="true" aria-label="Recadrer ta photo de profil"
      style={{ position: 'fixed', inset: 0, zIndex: 50, background: colors.bg, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24, color: colors.text, fontFamily: font.medium.fontFamily, fontWeight: 500 }}>
      <div style={{ fontSize: 20, fontWeight: 800 }}>Recadre ta photo</div>
      <div style={{ fontSize: 13, color: colors.muted, textAlign: 'center', maxWidth: size }}>Glisse pour déplacer, pince ou utilise le curseur pour zoomer.</div>
      {error ? <div role="alert" style={{ maxWidth: size, color: colors.coral, textAlign: 'center' }}>{error}</div> : (
        <canvas ref={canvas} aria-label="Aperçu du recadrage" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
          onWheel={(e) => zoomBy(e.deltaY < 0 ? 1.08 : 1 / 1.08)}
          style={{ width: size, height: size, touchAction: 'none', cursor: 'grab', borderRadius: 16, background: colors.bg }} />
      )}
      {img ? (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', width: size }}>
          {button('−', () => zoomBy(1 / 1.2), false, 'Dézoomer')}
          <input type="range" aria-label="Zoom" min={Math.log(fit.min)} max={Math.log(fit.max)} step={0.01} value={Math.log(view.scale)}
            onChange={(e) => setView((v) => ({ ...v, scale: clamp(Math.exp(Number(e.target.value))) }))} style={{ flex: 1, accentColor: colors.accent }} />
          {button('+', () => zoomBy(1.2), false, 'Zoomer')}
          {button('↻', () => setView((v) => ({ ...v, rot: (v.rot + 90) % 360 })), false, 'Pivoter d’un quart de tour')}
        </div>
      ) : null}
      <div style={{ display: 'flex', gap: 10 }}>
        {button('Annuler', onCancel)}
        {button('Valider la photo', done, true)}
      </div>
    </div>
  );
}

/** Dessine la photo (déplacée, zoomée, pivotée) dans un carré ; à l'écran, l'extérieur du cercle est assombri. */
function draw(ctx: CanvasRenderingContext2D, img: HTMLImageElement, v: { x: number; y: number; scale: number; rot: number }, size: number, k: number, preview: boolean) {
  const side = size * k;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = colors.bg;
  ctx.fillRect(0, 0, side, side);
  ctx.setTransform(k, 0, 0, k, (size / 2 + v.x) * k, (size / 2 + v.y) * k);
  ctx.rotate((v.rot * Math.PI) / 180);
  ctx.scale(v.scale, v.scale);
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
  if (!preview) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#000a';
  ctx.beginPath();
  ctx.rect(0, 0, side, side);
  ctx.arc(side / 2, side / 2, side / 2 - 2 * k, 0, Math.PI * 2, true);
  ctx.fill('evenodd');
  ctx.strokeStyle = '#fff8';
  ctx.lineWidth = 2 * k;
  ctx.beginPath();
  ctx.arc(side / 2, side / 2, side / 2 - 2 * k, 0, Math.PI * 2);
  ctx.stroke();
}
