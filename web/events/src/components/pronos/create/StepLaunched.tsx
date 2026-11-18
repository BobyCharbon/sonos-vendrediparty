import { router, type Href } from 'expo-router';
import { useState } from 'react';
import { Image, Platform, Pressable, Share, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PrimaryButton, Seal, useReducedMotion } from '@/components/pronos/Kit';
import { discussionsOn } from '@/lib/features';
import { palette } from '@/lib/groups';
import { pressTransition } from '@/lib/motion';
import { qrDataUri } from '@/lib/tickets';

import type { Award, Draft } from './model';
import { shownQuestion } from './model';
import { PreviewCard, type Place } from './PreviewCard';
import { C, rounded, Txt, web } from './ui';

/**
 * Étape 4 « C'est lancé ! » (maquette 2-4) : le sceau se pose, la carte telle que la bande la voit, puis le lien à
 * partager (construit depuis l'adresse du site, jamais un domaine en dur), la discussion, le partage, le QR, et
 * « Jouer maintenant » (l'organisateur joue aussi). Pas de confettis : ils sont réservés à une bonne réponse.
 * Aucune récompense pour le partage (Apple 3.2.2).
 */
export function StepLaunched({ id, linkPath, d, awards, place, closesAt, patates, told, chat, listPath }: {
  id: string; linkPath: string | null; d: Draft; awards: Award[]; place: Place; closesAt: string; patates: boolean;
  /** « Les 14 membres des Grenats sont prévenus. » */
  told: string; chat: string | null; listPath: string;
}) {
  const reduce = useReducedMotion();
  const [copied, setCopied] = useState(false);
  const [qr, setQr] = useState(false);
  const origin = typeof location !== 'undefined' ? location.origin : '';
  const url = linkPath ? `${origin}${linkPath}` : `${origin}/?tab=events&prono=${id}`;
  const shown = url.replace(/^https?:\/\//, '');
  const color = palette(place.group?.color ?? (place.event ? 'coral' : 'lavender'));
  const question = shownQuestion(d, awards);

  async function copy() {
    await navigator.clipboard?.writeText(url).catch(() => undefined);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  async function share() {
    if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
      await (navigator as Navigator).share({ title: 'Un prono pour toi', text: question, url }).catch(() => undefined);
    } else await Share.share({ message: `${question} ${url}` }).catch(() => undefined);
  }

  return (
    <SafeAreaView style={st.screen} edges={['top', 'left', 'right', 'bottom']}>
      <View style={[st.rays, !reduce && st.spin]} />
      <View style={st.nav}>
        <Pressable accessibilityRole="button" accessibilityLabel="Fermer" onPress={() => router.replace(listPath as Href)} style={st.round}>
          <Text style={{ color: C.t1, fontSize: 18, fontWeight: '600' }}>✕</Text>
        </Pressable>
        <Txt size={16} weight="600" color={C.t2} style={{ flex: 1, textAlign: 'center', marginRight: 44 }}>Prono lancé</Txt>
      </View>
      <View style={st.content}>
        <View style={[st.sealWrap, !reduce && st.drop]} testID="prono-launched">
          {!reduce ? <View style={[st.wave, { borderColor: color.main }]} /> : null}
          <Seal emoji={d.emoji} color={place.group?.color ?? 'lavender'} size={112} />
        </View>
        <View style={[{ gap: 10, alignItems: 'center' }, !reduce && st.fadeIn]}>
          <Text role="heading" aria-level={1} style={[rounded, { fontSize: 40, color: C.t1, textAlign: 'center' }]}>C’est lancé !</Text>
          <Txt size={17} color={C.t2} style={{ textAlign: 'center', lineHeight: 23 }}>
            <Text style={{ color: C.t1, fontWeight: '700' }}>{told} </Text>
            Les réponses restent scellées jusqu’au dévoilement.
          </Txt>
        </View>
        <View style={!reduce ? st.rise : undefined}>
          <PreviewCard d={d} awards={awards} place={place} closesAt={closesAt} patates={patates} launched />
        </View>

        <View style={[{ gap: 12 }, !reduce && st.fadeLate]}>
          <Txt size={14} weight="700" color={C.t2} style={{ letterSpacing: 1.2 }}>INVITE LA BANDE</Txt>
          <View style={st.linkBox}>
            <Txt size={16} color={C.t2}>⇪</Txt>
            <Txt size={16} weight="600" numberOfLines={1} style={{ flex: 1 }}>{shown}</Txt>
            <Pressable accessibilityRole="button" accessibilityLabel={copied ? 'Lien copié' : 'Copier le lien'} testID="prono-copy" onPress={() => void copy()}
              style={({ pressed }) => [st.copy, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
              <Txt size={16} weight="700" color="#fff">{copied ? 'Copié ✓' : '⧉ Copier'}</Txt>
            </Pressable>
          </View>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            {chat && discussionsOn ? (
              <Action icon="💬" label={place.event ? 'Discussion de la soirée' : 'Discussion du groupe'} onPress={() => router.push(chat as Href)} />
            ) : null}
            <Action icon="⇪" label="Partager…" onPress={() => void share()} />
            <Action icon="▦" label="QR code" onPress={() => setQr(!qr)} on={qr} />
          </View>
          {qr ? (
            <View style={st.qrBox}>
              <Image source={{ uri: qrDataUri(url) }} style={st.qr} accessibilityLabel="Code QR du prono" />
              <Txt size={14} color={C.t2} style={{ textAlign: 'center' }}>À scanner avec l’appareil photo du téléphone.</Txt>
            </View>
          ) : null}
        </View>

        <View style={{ gap: 6 }}>
          <PrimaryButton label="Jouer maintenant →" onPress={() => router.replace(`/prono/${id}` as Href)} testID="prono-play-now" />
          <Pressable accessibilityRole="button" onPress={() => router.replace(listPath as Href)} style={st.ghost} testID="prono-see-list">
            <Txt size={17} weight="700" color={C.lavText}>Voir mes pronos</Txt>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

function Action({ icon, label, onPress, on }: { icon: string; label: string; onPress: () => void; on?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [st.action, on && { borderColor: C.lav }, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
      <View style={st.actionIcon}><Text style={{ fontSize: 20, color: C.t1 }}>{icon}</Text></View>
      <Txt size={15} weight="600" style={{ textAlign: 'center' }}>{label}</Txt>
    </Pressable>
  );
}

const anim = (keyframes: object[], ms: number, delay = 0, curve = 'cubic-bezier(.34,1.45,.64,1)') => web({
  animationKeyframes: keyframes, animationDuration: `${ms}ms`, animationDelay: `${delay}ms`, animationTimingFunction: curve, animationFillMode: 'backwards',
});

const st = StyleSheet.create({
  screen: web({ flex: 1, backgroundColor: C.bg, overflow: 'hidden',
    backgroundImage: 'radial-gradient(70% 40% at 50% 12%, rgba(255,122,89,0.22), transparent 70%)' }),
  rays: web({ position: 'absolute', top: -260, left: '50%', width: 900, height: 900, marginLeft: -450, opacity: 0.1, pointerEvents: 'none',
    backgroundImage: 'repeating-conic-gradient(from 0deg, #fff 0deg 4deg, transparent 4deg 18deg)', borderRadius: 450 }),
  spin: web({ animationKeyframes: [{ from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } }], animationDuration: '40s',
    animationIterationCount: 'infinite', animationTimingFunction: 'linear' }),
  nav: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 64, width: '100%', maxWidth: 580, alignSelf: 'center' },
  round: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: C.glass, borderWidth: 1, borderColor: C.lineStrong },
  content: web({ flex: 1, overflowY: 'auto', paddingHorizontal: 20, paddingBottom: 24, gap: 24, width: '100%', maxWidth: 560, alignSelf: 'center' }),
  sealWrap: { alignSelf: 'center', alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  drop: anim([{ from: { opacity: 0, transform: 'scale(1.35)' }, to: { opacity: 1, transform: 'scale(1)' } }], 520, 120),
  wave: web({ position: 'absolute', width: 112, height: 112, borderRadius: 56, borderWidth: 2,
    animationKeyframes: [{ from: { opacity: 0.5, transform: 'scale(1)' }, to: { opacity: 0, transform: 'scale(3)' } }],
    animationDuration: '700ms', animationDelay: '120ms', animationTimingFunction: 'ease-out', animationFillMode: 'both' }),
  fadeIn: anim([{ from: { opacity: 0, transform: 'translateY(14px)' }, to: { opacity: 1, transform: 'none' } }], 550, 300),
  rise: anim([{ from: { opacity: 0, transform: 'translateY(24px)' }, to: { opacity: 1, transform: 'none' } }], 600, 420),
  fadeLate: anim([{ from: { opacity: 0 }, to: { opacity: 1 } }], 400, 600, 'ease-out'),
  linkBox: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 56, paddingLeft: 16, paddingRight: 6, borderRadius: 18,
    backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  copy: web({ height: 44, paddingHorizontal: 16, borderRadius: 14, justifyContent: 'center', backgroundColor: C.lavDeep,
    backgroundImage: 'linear-gradient(135deg, #8C7CFF, #6A5AE8)' }),
  action: { flex: 1, minHeight: 84, gap: 8, alignItems: 'center', justifyContent: 'center', padding: 10, borderRadius: 18,
    backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  actionIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.08)', alignItems: 'center', justifyContent: 'center' },
  qrBox: { alignItems: 'center', gap: 10, padding: 16, borderRadius: 22, backgroundColor: C.glass },
  qr: { width: 220, height: 220, borderRadius: 14 },
  ghost: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
});
