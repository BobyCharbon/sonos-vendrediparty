import { useState } from 'react';
import { Platform, ScrollView, Text, View } from 'react-native';

import { SheetBackdrop, SheetClose, useSheetSignal } from '@/components/SheetGesture';
import { initials } from '@/lib/format';
import type { Prono } from '@/lib/pronos';

import { FaceRing, GlassButton, PinkButton } from './Bits';
import { K, spring, useStage } from './fx';
import { dayLong, rarity, rightText, v2, type V2 } from './model';
import { N, round, terrainLook, text, web } from './theme';

/**
 * Carte à partager 9:16 « 🔮 J'avais vu juste » (maquette 4-partage) : la question, la bonne réponse, la rareté, mon
 * visage et la date. JAMAIS de patates (rien qui ressemble à un gain montré hors de l'app) ni le nom d'un autre joueur.
 * Partager ne rapporte rien (Apple 3.2.2). L'image (1080 × 1920) est dessinée à la main sur un canvas, sans bibliothèque.
 */
export function ShareCard({ prono }: { prono: Prono }) {
  return <CardView p={v2(prono)} />;
}

function CardView({ p }: { p: V2 }) {
  const d = shareData(p);
  const { root } = useStage((s) => {
    s.a('card', [{ transform: 'translateY(24px) scale(.94)', opacity: 0 }, { transform: 'none', opacity: 1 }], 0, spring(0.45, 0.8));
    s.a('orb', [{ transform: 'scale(.3)', opacity: 0 }, { transform: 'none', opacity: 1 }], 180, spring(0.3, 0.5));
    const dots = s.qa('dot');
    [...dots.filter((x) => x.dataset.on !== '1'), ...dots.filter((x) => x.dataset.on === '1')]
      .forEach((x, i) => s.a(x, [{ transform: 'scale(0)' }, { transform: 'scale(1)' }], 260 + i * 40, spring(0.3, 0.55)));
  }, 1000, [p.id]);
  const look = terrainLook(p.group);
  return (
    <View ref={root} style={{ alignItems: 'center' }}>
      <K k="card" role="img" testID="prono-share-card"
        aria-label={`Carte : J’avais vu juste. ${d.question} Bonne réponse : ${d.answer}. ${d.rare}.`}
        style={web({ width: 324, height: 576, borderRadius: 28, overflow: 'hidden', backgroundColor: '#140C2A',
          boxShadow: '0 30px 60px -20px rgba(0,0,0,.7), 0 0 0 1px rgba(255,255,255,.08)' })}>
        <View style={web({ position: 'absolute', width: 260, height: 260, left: -90, top: -70, borderRadius: 999, backgroundColor: look.to, opacity: 0.6, filter: 'blur(50px)' })} />
        <View style={web({ position: 'absolute', width: 240, height: 240, right: -110, top: 120, borderRadius: 999, backgroundColor: N.lav2, opacity: 0.6, filter: 'blur(50px)' })} />
        <View style={web({ position: 'absolute', width: 260, height: 200, left: -40, bottom: -110, borderRadius: 999, backgroundColor: look.from, opacity: 0.35, filter: 'blur(50px)' })} />
        <View style={{ flex: 1, alignItems: 'center', paddingHorizontal: 24, paddingVertical: 22 }}>
          <View style={{ width: '100%', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <Text style={[text(13, '900', 'rgba(255,255,255,0.72)'), { letterSpacing: 2 }]}>VENDREDI PARTY</Text>
            {d.terrain ? (
              <View style={{ height: 26, paddingHorizontal: 10, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.12)', borderWidth: 1,
                borderColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', maxWidth: 150 }}>
                <Text style={text(12, '600')} numberOfLines={1}>{d.terrain}</Text>
              </View>
            ) : null}
          </View>
          <K k="orb" style={web({ marginTop: 26, filter: 'drop-shadow(0 0 24px rgba(185,167,255,.9))' })}><Text style={{ fontSize: 72 }}>🔮</Text></K>
          <Text style={[round(40, 42), { marginTop: 12, color: '#FFFFFF', textAlign: 'center' }]}>J’avais vu juste</Text>
          <View style={{ marginTop: 20, width: '100%', padding: 14, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.08)', borderWidth: 1,
            borderColor: 'rgba(255,255,255,0.14)' }}>
            <Text style={[round(18, 22), { color: '#FFFFFF', textAlign: 'center' }]} numberOfLines={4}>{d.question}</Text>
          </View>
          <View style={web({ marginTop: 12, height: 52, flexDirection: 'row', alignItems: 'center', gap: 10, paddingLeft: 8, paddingRight: 18, borderRadius: 999,
            backgroundColor: N.mint, boxShadow: '0 10px 30px -8px rgba(91,227,166,.7)', maxWidth: '100%' })}>
            <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(29,21,48,0.14)', alignItems: 'center', justifyContent: 'center' }}>
              <Text style={text(16, '900', N.ink)}>✓</Text>
            </View>
            <Text style={[round(20, 24), { color: N.ink, flexShrink: 1 }]} numberOfLines={1}>{d.answer}</Text>
          </View>
          <View style={{ flexDirection: 'row', gap: 7, marginTop: 22, flexWrap: 'wrap', justifyContent: 'center' }} aria-hidden>
            {d.dots.map((on, i) => (
              <K key={i} k="dot" data={{ on: on ? '1' : '0' }} style={web({ width: 12, height: 12, borderRadius: 6, borderWidth: 1.5,
                borderColor: on ? N.mint : 'rgba(255,255,255,0.3)', backgroundColor: on ? N.mint : 'transparent',
                boxShadow: on ? '0 0 10px rgba(91,227,166,.8)' : 'none' })} />
            ))}
          </View>
          <Text style={[text(15, '700', N.lemon), { marginTop: 10 }]}>{d.rare}</Text>
          <View style={{ marginTop: 'auto', flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            {d.me ? (
              <View style={web({ borderRadius: 999, boxShadow: `0 0 0 3px #140C2A, 0 0 0 6px ${N.lemon}` })}><FaceRing face={d.me} size={52} ring="#140C2A" /></View>
            ) : null}
            <View>
              <Text style={text(16, '700', '#FFFFFF')}>{d.name}</Text>
              <Text style={text(13, '500', 'rgba(244,241,255,0.75)')}>{d.day}</Text>
            </View>
          </View>
        </View>
      </K>
    </View>
  );
}

/** La feuille « Partager » : la carte, « Partager… » (image), « Enregistrer ». */
export function ShareSheet({ prono, onClose }: { prono: V2; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  useSheetSignal(true);
  async function go(save: boolean) {
    setBusy(true);
    setNote(null);
    try {
      const blob = await shareImage(shareData(prono));
      if (!blob) throw new Error('canvas');
      const file = new File([blob], 'vendredi-party-prono.png', { type: 'image/png' });
      const nav = typeof navigator !== 'undefined' ? (navigator as Navigator & { canShare?: (d: ShareData) => boolean }) : null;
      if (!save && nav?.share && nav.canShare?.({ files: [file] })) {
        await nav.share({ files: [file], title: 'J’avais vu juste' }).catch(() => undefined);
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = file.name;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
        if (!save) setNote('Image enregistrée : tu peux la partager où tu veux.');
      }
    } catch {
      setNote('L’image n’a pas pu être créée. Réessaie dans un instant.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={web({ position: 'fixed', left: 0, right: 0, top: 0, bottom: 0, zIndex: 1100, justifyContent: 'flex-end' })} accessibilityViewIsModal aria-modal
      role="dialog" aria-label="Partager">
      <SheetBackdrop onPress={onClose} />
      <View style={{ maxHeight: '96%', backgroundColor: '#141029', borderTopLeftRadius: 28, borderTopRightRadius: 28, borderTopWidth: 1, borderColor: N.line2,
        width: '100%', maxWidth: 520, alignSelf: 'center' }}>
        <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
          <View style={{ alignItems: 'center', paddingTop: 8 }}><View style={{ width: 38, height: 5, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.25)' }} /></View>
          <View style={{ height: 52, alignItems: 'center', justifyContent: 'center' }}>
            <Text style={text(17, '700')}>Partager</Text>
            <SheetClose onPress={onClose} style={{ position: 'absolute', right: 12, top: 4, zIndex: 3 }} />
          </View>
          <CardView p={prono} />
          <View style={{ flexDirection: 'row', gap: 10, paddingHorizontal: 16, paddingTop: 16 }}>
            <PinkButton label={busy ? '…' : 'Partager…'} onPress={() => { if (!busy) void go(false); }} style={{ flex: 1 }} testID="prono-share-go" />
            <GlassButton label="Enregistrer" onPress={() => { if (!busy) void go(true); }} style={{ flex: 1, height: 52 }} testID="prono-share-save" />
          </View>
          {note ? <Text style={[text(13, '500', N.t2), { textAlign: 'center', marginTop: 10, paddingHorizontal: 16 }]}>{note}</Text> : null}
          <Text style={[text(13, '500', N.t2), { textAlign: 'center', marginTop: 10 }]}>Pour la gloire : partager ne rapporte rien.</Text>
        </ScrollView>
      </View>
    </View>
  );
}

type ShareData = { question: string; answer: string; rare: string; dots: boolean[]; me: V2['answered'][number] | null; name: string; day: string;
  terrain: string | null; from: string; to: string };

function shareData(p: V2): ShareData {
  const r = rarity(p);
  const meFace = (p.answers ?? []).find((a) => a.user.me)?.user ?? p.answered.find((f) => f.me) ?? null;
  const n = Math.min(r.of, 12);
  const on = Math.min(r.right, n);
  const look = terrainLook(p.group);
  // Une personne (« Qui arrive en dernier ? ») : jamais le nom d'un autre sur la carte.
  const label = p.kind === 'person' || p.kind === 'award' || p.kind === 'text' ? '' : rightText(p);
  return {
    question: p.question,
    answer: label || 'Bonne réponse',
    rare: r.right * 2 <= r.of ? `Seuls ${r.right} sur ${r.of} l’avaient vu` : `${r.right} sur ${r.of} l’avaient vu`,
    dots: Array.from({ length: n }, (_, i) => i < on),
    me: meFace,
    name: meFace?.name ?? 'Moi',
    day: dayLong(p.result?.at ?? p.closes_at),
    terrain: p.group ? `${p.group.emoji} ${p.group.name}` : p.event ? `🎉 ${p.event.title}` : null,
    from: look.from,
    to: look.to,
  };
}

/** L'image de la carte, 1080 × 1920, dessinée à la main (pas de bibliothèque, pas de photo d'un autre). */
async function shareImage(d: ShareData): Promise<Blob | null> {
  if (Platform.OS !== 'web' || typeof document === 'undefined') return null;
  const S = 1080 / 324;
  const c = document.createElement('canvas');
  c.width = 1080;
  c.height = 1920;
  const g = c.getContext('2d');
  if (!g) return null;
  g.scale(S, S);
  g.fillStyle = '#140C2A';
  g.fillRect(0, 0, 324, 576);
  const blob = (x: number, y: number, r: number, color: string, alpha: number) => {
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, hexA(color, alpha));
    grd.addColorStop(1, hexA(color, 0));
    g.fillStyle = grd;
    g.fillRect(x - r, y - r, r * 2, r * 2);
  };
  blob(40, 60, 190, d.to, 0.6);
  blob(330, 240, 180, '#7B6CF6', 0.55);
  blob(90, 560, 170, d.from, 0.35);
  const sans = '-apple-system, BlinkMacSystemFont, system-ui, sans-serif';
  const rounded = 'ui-rounded, "SF Pro Rounded", -apple-system, system-ui, sans-serif';
  g.textBaseline = 'alphabetic';
  g.fillStyle = 'rgba(255,255,255,0.72)';
  g.font = `900 13px ${sans}`;
  g.textAlign = 'left';
  spaced(g, 'VENDREDI PARTY', 24, 40, 2);
  if (d.terrain) {
    g.font = `600 12px ${sans}`;
    const t = fit(g, d.terrain, 140);
    const w = g.measureText(t).width + 20;
    pill(g, 300 - w, 23, w, 26, 'rgba(255,255,255,0.12)');
    g.fillStyle = '#FFFFFF';
    g.fillText(t, 310 - w, 41);
  }
  g.textAlign = 'center';
  g.font = `72px ${sans}`;
  g.shadowColor = 'rgba(185,167,255,0.9)';
  g.shadowBlur = 24;
  g.fillText('🔮', 162, 150);
  g.shadowBlur = 0;
  g.fillStyle = '#FFFFFF';
  g.font = `800 38px ${rounded}`;
  g.fillText('J’avais vu juste', 162, 210);
  g.font = `800 18px ${rounded}`;
  const lines = wrap(g, d.question, 248).slice(0, 4);
  const qh = 28 + lines.length * 22;
  pill(g, 24, 232, 276, qh, 'rgba(255,255,255,0.08)', 20);
  g.fillStyle = '#FFFFFF';
  lines.forEach((l, i) => g.fillText(l, 162, 260 + i * 22));
  const ay = 232 + qh + 12;
  g.font = `800 20px ${rounded}`;
  const ans = fit(g, d.answer, 210);
  const aw = Math.min(276, g.measureText(ans).width + 70);
  pill(g, 162 - aw / 2, ay, aw, 52, '#5BE3A6');
  g.fillStyle = 'rgba(29,21,48,0.14)';
  g.beginPath();
  g.arc(162 - aw / 2 + 26, ay + 26, 18, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#1D1530';
  g.font = `900 16px ${sans}`;
  g.fillText('✓', 162 - aw / 2 + 26, ay + 32);
  g.font = `800 20px ${rounded}`;
  g.textAlign = 'left';
  g.fillText(ans, 162 - aw / 2 + 52, ay + 33);
  g.textAlign = 'center';
  const dy = ay + 52 + 28;
  const n = d.dots.length;
  d.dots.forEach((on, i) => {
    const x = 162 - ((n - 1) * 19) / 2 + i * 19;
    g.beginPath();
    g.arc(x, dy, 6, 0, Math.PI * 2);
    if (on) { g.fillStyle = '#5BE3A6'; g.fill(); } else { g.strokeStyle = 'rgba(255,255,255,0.3)'; g.lineWidth = 1.5; g.stroke(); }
  });
  g.fillStyle = '#FFE27A';
  g.font = `700 15px ${sans}`;
  g.fillText(d.rare, 162, dy + 30);
  // Moi : initiales sur l'anneau citron (jamais de photo d'un autre, ni de nom d'un autre).
  g.fillStyle = '#FFE27A';
  g.beginPath();
  g.arc(60, 520, 32, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#140C2A';
  g.beginPath();
  g.arc(60, 520, 29, 0, Math.PI * 2);
  g.fill();
  const grd = g.createLinearGradient(34, 494, 86, 546);
  grd.addColorStop(0, '#CBBDFF');
  grd.addColorStop(1, '#7B6CF6');
  g.fillStyle = grd;
  g.beginPath();
  g.arc(60, 520, 26, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#1D1530';
  g.font = `800 20px ${rounded}`;
  g.fillText(initials(d.name), 60, 527);
  g.textAlign = 'left';
  g.fillStyle = '#FFFFFF';
  g.font = `700 16px ${sans}`;
  g.fillText(fit(g, d.name, 200), 102, 515);
  g.fillStyle = 'rgba(244,241,255,0.75)';
  g.font = `500 13px ${sans}`;
  g.fillText(d.day, 102, 534);
  return new Promise((resolve) => c.toBlob((b) => resolve(b), 'image/png'));
}

function hexA(hex: string, a: number): string {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((x) => x + x).join('') : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function pill(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, fill: string, r = h / 2) {
  g.fillStyle = fill;
  g.beginPath();
  g.roundRect(x, y, w, h, r);
  g.fill();
}

function spaced(g: CanvasRenderingContext2D, s: string, x: number, y: number, gap: number) {
  let cx = x;
  for (const ch of s) {
    g.fillText(ch, cx, y);
    cx += g.measureText(ch).width + gap;
  }
}

function fit(g: CanvasRenderingContext2D, s: string, max: number): string {
  if (g.measureText(s).width <= max) return s;
  let t = s;
  while (t.length > 1 && g.measureText(`${t}…`).width > max) t = t.slice(0, -1);
  return `${t}…`;
}

function wrap(g: CanvasRenderingContext2D, s: string, max: number): string[] {
  const out: string[] = [];
  let line = '';
  for (const w of s.split(/\s+/)) {
    const next = line ? `${line} ${w}` : w;
    if (g.measureText(next).width > max && line) { out.push(line); line = w; } else line = next;
  }
  if (line) out.push(line);
  return out;
}
