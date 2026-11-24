import { useCallback, useRef, useState, type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { Button, T } from '@/components/ui';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * Didacticiel des Souvenirs (24.11), sur le modèle de celui de l'Agenda (components/agenda/Tutorial.tsx) : 5 cartes, une
 * idée par carte, + 2 cartes pour l'organisation (`staff`). Il s'ouvre à chaque ouverture de la carte Souvenirs tant que la
 * personne n'a pas touché « Ne plus me le rappeler » (retenu sur cet appareil : pas de table de préférences des Souvenirs) ;
 * ✕ / « Passer » / « C'est compris » le ferment pour cette fois. « ❔ Comment ça marche » le rouvre (carte et réglages).
 * `keep` : enregistrement autorisé (cartes 3 et 4 changent quand il est coupé).
 */
export const TUTORIAL_READY = true;

const FILM = '#FFB547';
const ORANGE = '#FF9F43';

type Step = { key: string; title: string; text: ReactNode; art: ReactNode };

function steps(staff: boolean, keep: boolean): Step[] {
  const list: Step[] = [
    {
      key: 'quoi', title: 'Les photos de la soirée',
      text: <>Chacun prend des photos pendant la soirée. Personne ne les voit avant le dévoilement : <B>c’est la surprise</B>.</>,
      art: (
        <View style={st.film}>
          {['?', '?', '?', '?'].map((q, k) => <View key={k} style={st.frame}><T size={20} weight="bold" color={FILM}>{q}</T></View>)}
        </View>
      ),
    },
    {
      key: 'poses', title: '3 photos chacun',
      text: <>Comme un appareil jetable : une fois prise, <B>tu ne revois pas ta photo</B>. Tu peux l’annuler pendant 5 secondes.</>,
      art: (
        <View style={{ alignItems: 'center', gap: 10 }}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {[true, false, false].map((used, k) => <View key={k} style={[st.pose, used && st.poseUsed]} />)}
          </View>
          <View style={st.undo}><T size={13} weight="semibold">🧪 Partie au labo · ↩︎ Annuler (5 s)</T></View>
        </View>
      ),
    },
    {
      key: 'story', title: 'Le dévoilement',
      text: keep
        ? <><B>24 h après la fin</B>, tout le monde reçoit la story, visible 24 h. Touche ⭐ pour garder les photos des autres.</>
        : <><B>24 h après la fin</B>, tout le monde reçoit la story, visible 24 h. Ici, on regarde seulement : rien ne se garde.</>,
      art: (
        <View style={{ width: '100%', gap: 10, alignItems: 'center' }}>
          <View style={st.bars}>
            {[1, 1, 0.5, 0, 0].map((f, k) => <View key={k} style={st.bar}><View style={[st.barFill, { width: `${f * 100}%` }]} /></View>)}
          </View>
          <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
            <T size={13} muted>Visible encore 23 h</T>
            {keep ? <View style={st.star}><T size={13} weight="bold" color={colors.onCoral}>⭐ Garder</T></View> : null}
          </View>
        </View>
      ),
    },
    {
      key: 'mes', title: 'Tes souvenirs',
      text: keep
        ? <>Sur la fiche de l’événement, tu retrouves <B>tes photos et celles que tu as gardées</B>, à enregistrer sur ton appareil.</>
        : <>L’organisateur a coupé l’enregistrement : <B>après la story, rien ne reste</B>, ni chez toi ni chez les autres.</>,
      art: keep ? (
        <View style={{ gap: 6, width: '100%' }}>
          <Line icon="📸" label="Ta photo" when="21 h 40" />
          <Line icon="⭐" label="Gardée · photo de Maé" when="22 h 15" />
        </View>
      ) : (
        <View style={st.warn}><T size={14} weight="bold" color={ORANGE}>⚠️ Enregistrement désactivé</T></View>
      ),
    },
    {
      key: 'confiance', title: 'En confiance',
      text: <>Une photo te gêne ? « Signaler », puis « Je suis sur la photo… » : <B>elle est aussitôt masquée</B>. L’organisation peut voir les photos avant le dévoilement.</>,
      art: (
        <View style={{ alignItems: 'center', gap: 8 }}>
          <View style={st.report}><T size={13} weight="semibold">🚩 Je suis sur la photo…</T></View>
          <T size={13} weight="semibold" color={colors.mint}>✓ Masquée pour tous</T>
        </View>
      ),
    },
  ];
  if (!staff) return list;
  return [
    ...list,
    {
      key: 'regler', title: 'Organisation : les réglages',
      text: <>Dans « Modifier », allume <B>📸 Souvenirs</B>. « Autoriser l’enregistrement » est allumé : chacun garde ses préférées. Coupé, rien ne reste après la story. Tout se fige à la 1re photo.</>,
      art: (
        <View style={{ gap: 6, width: '100%' }}>
          <Switch label="📸 Souvenirs" />
          <Switch label="Autoriser l’enregistrement" />
        </View>
      ),
    },
    {
      key: 'relire', title: 'Organisation : relire et dévoiler',
      text: <><B>« 👀 Relire les photos »</B> : tu les vois avant tout le monde et tu retires celles qui ne vont pas. Après la fin, <B>« Dévoiler maintenant »</B> avance la story.</>,
      art: (
        <View style={{ gap: 6, width: '100%' }}>
          <View style={[st.line, { justifyContent: 'center' }]}><T size={14} weight="semibold">👀 Relire les photos (12)</T></View>
          <View style={[st.line, { backgroundColor: colors.action, justifyContent: 'center' }]}><T size={14} weight="semibold" color={colors.onAction}>Dévoiler maintenant</T></View>
        </View>
      ),
    },
  ];
}

function B({ children }: { children: ReactNode }) {
  return <Text style={{ ...font.bold, color: colors.text }}>{children}</Text>;
}

function Line({ icon, label, when }: { icon: string; label: string; when: string }) {
  return (
    <View style={st.line}>
      <T size={16}>{icon}</T>
      <T size={14} weight="semibold" style={{ flex: 1 }} numberOfLines={1}>{label}</T>
      <T size={13} muted>{when}</T>
    </View>
  );
}

function Switch({ label }: { label: string }) {
  return (
    <View style={st.line}>
      <T size={14} weight="semibold" style={{ flex: 1 }} numberOfLines={1}>{label}</T>
      <View style={st.switch}><View style={st.knob} /></View>
    </View>
  );
}

/** La fenêtre du didacticiel. `onSkip` : fermé pour cette fois ; `onNever` : « Ne plus me le rappeler ». */
export function SouvenirsTutorial({ visible, staff, keep, onSkip, onNever }: {
  visible: boolean; staff: boolean; keep: boolean; onSkip: () => void; onNever: () => void;
}) {
  if (!visible) return null;
  return <Sheet staff={staff} keep={keep} onSkip={onSkip} onNever={onNever} />;
}

function Sheet({ staff, keep, onSkip, onNever }: { staff: boolean; keep: boolean; onSkip: () => void; onNever: () => void }) {
  const list = steps(staff, keep);
  const [i, setI] = useState(0);
  const card = useRef<View>(null);
  const scroller = useRef<ScrollView>(null);
  const sheetTop = useSheetTop();
  useSheetDrag(true, onSkip, card, scroller);
  useSheetSignal(true);
  const step = list[i];
  const last = i === list.length - 1;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onSkip}>
      <View style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={onSkip} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Comment marchent les Souvenirs" testID="souvenirs-tutorial">
          <SheetTop onClose={onSkip} label="Passer le tutoriel" />
          <ScrollView ref={scroller} contentContainerStyle={{ gap: 14 }}>
            <View key={step.key} style={[{ gap: 14 }, enter('rise')]} testID={`souvenirs-tutorial-step-${i + 1}`}>
              <View style={st.art} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">{step.art}</View>
              <View style={{ gap: 6 }} accessibilityLiveRegion="polite">
                <T size={13} weight="bold" color={colors.accentSoft}>{`${i + 1} / ${list.length}`}</T>
                <Text role="heading" aria-level={2} style={st.title}>{step.title}</Text>
                <T size={16} color={colors.textSoft} style={{ lineHeight: 23 }}>{step.text}</T>
              </View>
            </View>
            <View style={st.dots} accessibilityLabel={`Étape ${i + 1} sur ${list.length}`}>
              {list.map((s, k) => <View key={s.key} style={[st.dotNav, k === i && st.dotOn]} />)}
            </View>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {i ? <Button label="‹ Retour" variant="secondary" style={{ flex: 1 }} onPress={() => setI(i - 1)} />
                : <Button label="Passer" variant="secondary" style={{ flex: 1 }} onPress={onSkip} />}
              {last ? <Button label="C’est compris" style={{ flex: 2 }} onPress={onSkip} />
                : <Button label="Suivant" style={{ flex: 2 }} onPress={() => setI(i + 1)} />}
            </View>
            <Pressable accessibilityRole="button" onPress={onNever} style={({ pressed }) => [st.never, pressTransition, pressed && { opacity: 0.7 }]}>
              <T size={14} weight="semibold" color={colors.muted}>Ne plus me le rappeler</T>
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const OFF_KEY = 'party-souvenirs-tutorial-off';

/**
 * Ouvert d'office à chaque montage (`auto`) tant que « Ne plus me le rappeler » n'est pas retenu sur cet appareil
 * (stockage indisponible : il ne s'ouvre qu'à la demande). `show` : « ❔ Comment ça marche ».
 */
export function useSouvenirsTutorial(auto = true) {
  const [open, setOpen] = useState(() => {
    if (!auto) return false;
    try { return localStorage.getItem(OFF_KEY) !== '1'; } catch { return false; }
  });
  const never = useCallback(() => {
    try { localStorage.setItem(OFF_KEY, '1'); } catch { /* sans stockage : fermé pour cette page */ }
    setOpen(false);
  }, []);
  return { visible: open, show: useCallback(() => setOpen(true), []), skip: useCallback(() => setOpen(false), []), never };
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.88)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: { width: '100%', maxWidth: 480, maxHeight: '92%', gap: 8, padding: 20, paddingBottom: 24, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  art: { minHeight: 132, alignItems: 'center', justifyContent: 'center', padding: 16, borderRadius: radius.lg, backgroundColor: colors.bg,
    borderWidth: 1, borderColor: colors.line },
  title: { color: colors.text, fontFamily: 'BricolageGrotesque_800ExtraBold', fontSize: 26, letterSpacing: -0.3 },
  film: { flexDirection: 'row', gap: 6, padding: 8, borderRadius: 8, backgroundColor: '#0B0816', borderTopWidth: 3, borderBottomWidth: 3, borderColor: '#3a2f55', borderStyle: 'dashed' },
  frame: { width: 46, height: 58, borderRadius: 6, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface2 },
  pose: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: FILM, backgroundColor: FILM },
  poseUsed: { backgroundColor: 'transparent', borderColor: colors.lineStrong },
  undo: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: colors.surface },
  bars: { flexDirection: 'row', gap: 4, width: '100%', maxWidth: 240 },
  bar: { flex: 1, height: 4, borderRadius: 2, overflow: 'hidden', backgroundColor: colors.lineStrong },
  barFill: { height: 4, backgroundColor: '#fff' },
  star: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill, backgroundColor: FILM },
  line: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, minHeight: 40, borderRadius: radius.md, backgroundColor: colors.surface },
  warn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: radius.md, borderWidth: 1.5, borderColor: ORANGE, backgroundColor: 'rgba(255,159,67,0.13)' },
  report: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: colors.redDim },
  switch: { width: 40, height: 24, borderRadius: 12, padding: 2, backgroundColor: colors.mint, alignItems: 'flex-end' },
  knob: { width: 20, height: 20, borderRadius: 10, backgroundColor: '#fff' },
  dots: { flexDirection: 'row', gap: 6, justifyContent: 'center' },
  dotNav: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.lineStrong },
  dotOn: { width: 22, backgroundColor: colors.accent },
  never: { alignSelf: 'center', minHeight: 44, paddingHorizontal: 12, justifyContent: 'center' },
});
