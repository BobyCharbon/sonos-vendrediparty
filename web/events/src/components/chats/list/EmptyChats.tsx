import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { alpha, chatFont, useNeon, web, type NeonColors } from '../neon';
import { PersonFace } from './Faces';
import { Icon } from './Icons';
import { usePersonText } from '@/components/PersonName';
import type { ChatPerson } from '@/lib/chatList';
import { enter, pressTransition, reducedMotion } from '@/lib/motion';

const CONFETTI: { left: number; top: number; color: string; square?: boolean; rotate?: number; dot?: boolean }[] = [
  { left: 52, top: 40, color: '#FF4F9A' }, { left: 300, top: 36, color: '#FFE27A', square: true },
  { left: 340, top: 84, color: '#5BE3A6', rotate: 30 }, { left: 38, top: 150, color: '#6CC7FF', square: true },
  { left: 176, top: 8, color: '#FFB347', rotate: -20 }, { left: 92, top: 176, color: '#B9A7FF', dot: true }, { left: 268, top: 6, color: '#FF8FC0', dot: true },
];

/**
 * État vide (maquette 5-vide) : deux bulles néon qui se répondent, « Ta première discussion commence ici », jusqu'à 3
 * personnes croisées à une soirée avec « Écrire » (jamais tout le site), puis Nouveau message / Groupe.
 */
export function EmptyChats({ crossed, onWrite, onNew, onGroup }: {
  crossed: ChatPerson[]; onWrite: (p: ChatPerson) => Promise<void>; onNew: () => void; onGroup: () => void;
}) {
  const c = useNeon();
  const personText = usePersonText();
  const [busy, setBusy] = useState<string | null>(null);
  const subs = [...new Set(crossed.map((p) => p.sub).filter(Boolean))];
  const heading = subs.length === 1 ? `Croisés à ${subs[0]}` : 'Croisés récemment';
  return (
    <View style={{ paddingBottom: 32 }}>
      <View style={st.hero} aria-hidden>
        <View style={[st.glow, web({ backgroundImage: `radial-gradient(closest-side, rgba(123,108,246,.45), rgba(255,79,154,.14) 60%, transparent)`, filter: 'blur(8px)' })]} />
        <View style={[st.b1, { backgroundColor: c.theirs, borderColor: 'rgba(185,167,255,.55)' },
          web({ boxShadow: '0 0 0 4px rgba(185,167,255,.06), 0 0 30px -6px rgba(185,167,255,.7), 0 20px 40px -20px #000' }), float(0, -5)]}>
          <Text style={[chatFont.semibold, st.bt, { color: c.t1 }]}>Ça te dit vendredi ?</Text>
        </View>
        <View style={[st.b2, web({ backgroundImage: `linear-gradient(160deg, ${c.mineA}, ${c.mineB})`,
          boxShadow: '0 0 0 1.5px rgba(255,143,192,.7), 0 0 34px -4px rgba(255,79,154,.75), 0 20px 40px -20px #000' }), float(900, 4)]}>
          <Text style={[chatFont.semibold, st.bt, { color: '#fff' }]}>Grave ! 🎉</Text>
        </View>
        {CONFETTI.map((k, i) => (
          <View key={i} style={[{ position: 'absolute', left: `${(k.left / 390) * 100}%`, top: k.top, backgroundColor: k.color, opacity: k.dot ? 0.85 : 0.9 },
            k.dot ? { width: 8, height: 8, borderRadius: 4 } : k.square ? { width: 10, height: 10, borderRadius: 3, transform: [{ rotate: '45deg' }] }
              : { width: 14, height: 6, borderRadius: 3, transform: [{ rotate: `${k.rotate ?? 0}deg` }] },
            k.dot ? null : web({ boxShadow: `0 0 12px ${k.color}` })]} />
        ))}
      </View>

      <View style={[st.copy, enter('rise', 1)]}>
        <Text role="heading" aria-level={2} style={[chatFont.display, st.h2, { color: c.t1 }]}>Ta première discussion{'\n'}commence ici</Text>
        <Text style={[chatFont.text, st.p, { color: c.t2 }]}>Écris à quelqu’un croisé à une soirée, ou réunis ta bande dans un groupe.</Text>
      </View>

      {crossed.length ? (
        <View style={[st.sug, { backgroundColor: c.glass, borderColor: c.glassLine }, enter('rise', 2)]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Icon name="sparkle" size={13} color={c.t3} />
            <Text numberOfLines={1} style={[chatFont.label, { color: c.t3, flex: 1 }]}>{heading}</Text>
          </View>
          <View style={st.sugRow}>
            {crossed.map((p) => {
              const name = personText(p.id, p.name).split(' ')[0] ?? p.name;
              return (
                <View key={p.id} style={st.sp}>
                  <PersonFace id={p.id} name={p.name} photo={p.photo} size={40} />
                  <Text numberOfLines={1} style={[chatFont.semibold, { color: c.t1, fontSize: 15 }]}>{name}</Text>
                  <WriteButton c={c} label={`Écrire à ${name}`} busy={busy === p.id}
                    onPress={() => { setBusy(p.id); void onWrite(p).finally(() => setBusy(null)); }} />
                </View>
              );
            })}
          </View>
        </View>
      ) : null}

      <View style={[st.ctas, enter('rise', 3)]}>
        <Pressable accessibilityRole="button" accessibilityLabel="Nouveau message" onPress={onNew}
          style={({ pressed }) => [st.btn, { flex: 1 }, web({ backgroundImage: `linear-gradient(135deg, ${c.pinkA}, ${c.pink})`,
            boxShadow: '0 0 0 1px rgba(255,255,255,.25) inset, 0 14px 30px -12px rgba(255,79,154,.8)' }), pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
          <Icon name="compose" size={22} color={c.onPink} stroke={2.2} />
          <Text style={[chatFont.bold, { color: c.onPink, fontSize: 17 }]}>Nouveau message</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Nouveau groupe" onPress={onGroup}
          style={({ pressed }) => [st.btn, { paddingHorizontal: 16, backgroundColor: c.glass, borderWidth: 1, borderColor: c.glassLine }, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
          <Icon name="users" size={16} color={c.lav} />
          <Text style={[chatFont.semibold, { color: c.t1, fontSize: 15 }]}>Groupe</Text>
        </Pressable>
      </View>
    </View>
  );
}

function WriteButton({ c, label, busy, onPress }: { c: NeonColors; label: string; busy: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={busy} onPress={onPress}
      style={({ pressed }) => [st.write, { backgroundColor: alpha('#B9A7FF', 0.14), borderColor: alpha('#B9A7FF', 0.25) }, busy && { opacity: 0.6 },
        pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
      <Icon name="chat" size={16} color={c.lav} />
      <Text style={[chatFont.bold, { color: c.lav, fontSize: 14 }]}>Écrire</Text>
    </Pressable>
  );
}

/** Les bulles flottent doucement (rien avec « Réduire les animations »). */
function float(delay: number, rotate: number) {
  if (reducedMotion) return null;
  const at = (y: number) => ({ transform: `rotate(${rotate}deg) translateY(${y}px)` });
  return web({ animationKeyframes: [{ '0%': at(0), '50%': at(-6), '100%': at(0) }],
    animationDuration: '4200ms', animationIterationCount: 'infinite', animationTimingFunction: 'cubic-bezier(.45,0,.55,1)', animationDelay: `${delay}ms` });
}

const st = StyleSheet.create({
  hero: { position: 'relative', height: 196, marginTop: 8 },
  glow: { position: 'absolute', left: '50%', top: '50%', width: 300, height: 200, marginLeft: -150, marginTop: -100, borderRadius: 150 },
  b1: { position: 'absolute', left: '10%', top: 52, transform: [{ rotate: '-5deg' }], paddingVertical: 14, paddingHorizontal: 20,
    borderRadius: 26, borderBottomLeftRadius: 8, borderWidth: 1.5 },
  b2: { position: 'absolute', right: '12%', top: 112, transform: [{ rotate: '4deg' }], paddingVertical: 14, paddingHorizontal: 20,
    borderRadius: 26, borderBottomRightRadius: 8 },
  bt: { fontSize: 19, letterSpacing: -0.3 },
  copy: { alignItems: 'center', paddingHorizontal: 28, paddingTop: 6 },
  h2: { fontSize: 28, lineHeight: 32, letterSpacing: -0.8, textAlign: 'center' },
  p: { marginTop: 10, fontSize: 17, lineHeight: 23, textAlign: 'center' },
  sug: { marginHorizontal: 16, marginTop: 22, padding: 14, borderRadius: 22, borderWidth: 1 },
  sugRow: { flexDirection: 'row', marginTop: 12, gap: 8 },
  sp: { flex: 1, alignItems: 'center', gap: 6, minWidth: 0 },
  write: { height: 44, paddingHorizontal: 12, borderRadius: 22, borderWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  ctas: { flexDirection: 'row', gap: 10, paddingHorizontal: 16, paddingTop: 18 },
  btn: { height: 54, borderRadius: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
});
