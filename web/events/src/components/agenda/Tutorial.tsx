import { router, type Href } from 'expo-router';
import { useRef, useState, type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { hatched } from '@/components/agenda/Bits';
import { SheetBackdrop, SheetTop, useSheetDrag, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { Button, T } from '@/components/ui';
import { nativeAgenda, nativeAccess, rpc, type Calendar, type Sharing, type SharingGroup } from '@/lib/agenda';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * Tutoriel de l'Agenda (demande de l'admin du 23.11) : 5 cartes simples, à chaque arrivée sur l'Agenda tant que la
 * personne n'a pas touché « Ne plus me le rappeler » (`prefs.tutorial_off`). ✕ / « Passer » ferme pour cette fois.
 * Puis l'assistant « Configurer mon agenda en 3 étapes » : il renvoie vers les écrans existants avec `?setup=1`
 * (Calendriers, Partager), qui montrent la barre `SetupBar`, et finit sur /agenda/setup (« C'est prêt »).
 */

type Step = { key: string; title: string; text: ReactNode; art: ReactNode };

function steps(iphone: boolean): Step[] {
  return [
    {
      key: 'agenda', title: 'Ton agenda Party',
      text: <>Ton agenda dans Party, <B>visible par toi seul</B>. Tes soirées s’y mettent toutes seules (Présent, Peut-être, ce que tu organises). Tes autres rendez-vous : « + Ajouter ».</>,
      art: (
        <View style={{ gap: 6, width: '100%' }}>
          <Row dot={colors.accent} label="🎉 Apéro de la bande" when="ven. 20 h" />
          <Row dot={colors.mint} label="🦷 Dentiste" when="mar. 12 h" />
        </View>
      ),
    },
    {
      key: 'relier', title: 'Relie tes agendas',
      text: iphone
        ? <>Relie ton iPhone : Party voit quand tu es <B>pris</B>. Tes rendez-vous restent sur ton iPhone, <B>rien n’est envoyé</B> tant que tu ne partages pas. Et même là, seul « occupé » part : jamais le titre ni le lieu.</>
        : <>Ajoute ton agenda Google, iCloud ou Outlook avec son lien : Party voit quand tu es <B>pris</B>. <B>Rien n’est envoyé</B> tant que tu ne partages pas. Et même là, seul « occupé » part : jamais le titre ni le lieu.</>,
      art: (
        <View style={{ alignItems: 'center', gap: 8 }}>
          <View style={st.flow}>
            <View style={st.flowBox}><T size={26}>{iphone ? '📱' : '🗓️'}</T></View>
            <T size={20} color={colors.muted}>→</T>
            <View style={[st.busy, hatched]}><Text style={st.busyText}>Occupé</Text></View>
          </View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {['le titre', 'le lieu'].map((w) => <View key={w} style={st.never}><Text style={st.neverText}>✕ {w}</Text></View>)}
          </View>
        </View>
      ),
    },
    {
      key: 'partager', title: 'Partage tes dispos',
      text: <>Tu choisis <B>groupe par groupe</B>, rien n’est partagé d’office. Le groupe voit seulement « Disponible » ou « Occupé » : <B>jamais le titre ni le lieu</B>. Tu arrêtes quand tu veux, tout est effacé.</>,
      art: (
        <View style={{ gap: 6, width: '100%' }}>
          <Check on label="⚽ Potes du foot" />
          <Check label="🏡 La famille" />
        </View>
      ),
    },
    {
      key: 'libre', title: 'Qui est libre ?',
      text: <>Choisis un groupe : <B>plus un jour est vert</B>, plus il y a de monde libre. Le meilleur jour est encadré. Touche un jour pour voir qui est libre, puis « Organiser » ou « Faire voter ». Seuls ceux qui partagent leurs dispos comptent.</>,
      art: (
        <View style={st.cells}>
          {[0.15, 0.35, 0.9, 0.5, 0.2, 0.65, 0.3].map((a, i) => (
            <View key={i} style={[st.cell, { backgroundColor: `rgba(91,227,166,${a})` }, i === 2 && st.cellBest]}>
              {i === 2 ? <T size={12} weight="bold" color={colors.onMint}>★</T> : null}
            </View>
          ))}
        </View>
      ),
    },
    {
      key: 'liens', title: 'Liens de dispo (si tu veux)',
      text: <>Pour quelqu’un <B>hors de Party</B> (un client, ton coach…) : envoie-lui un lien qui montre tes créneaux libres, rien d’autre. Si tu l’autorises, la personne te demande un rendez-vous, et tu acceptes ou refuses.</>,
      art: (
        <View style={{ alignItems: 'center', gap: 8 }}>
          <View style={st.link}><T size={14} weight="semibold" color={colors.accentSoft}>🔗 …/agenda/toi/cafe</T></View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {['mar. 18 h', 'mer. 12 h', 'jeu. 19 h'].map((w) => <View key={w} style={st.slot}><T size={12} weight="semibold" color={colors.mint}>{w}</T></View>)}
          </View>
        </View>
      ),
    },
  ];
}

function B({ children }: { children: ReactNode }) {
  return <Text style={{ ...font.bold, color: colors.text }}>{children}</Text>;
}

function Row({ dot, label, when }: { dot: string; label: string; when: string }) {
  return (
    <View style={st.row}>
      <View style={[st.dot, { backgroundColor: dot }]} />
      <T size={14} weight="semibold" style={{ flex: 1 }} numberOfLines={1}>{label}</T>
      <T size={13} muted>{when}</T>
    </View>
  );
}

function Check({ on, label }: { on?: boolean; label: string }) {
  return (
    <View style={st.row}>
      <View style={[st.box, on && st.boxOn]}>{on ? <Text style={{ color: '#fff', fontSize: 14, ...font.bold }}>✓</Text> : null}</View>
      <T size={14} weight="semibold" style={{ flex: 1 }} numberOfLines={1}>{label}</T>
    </View>
  );
}

/** La fenêtre du tutoriel. `onSkip` : fermé pour cette fois ; `onNever` : « Ne plus me le rappeler » ; `onSetup` : l'assistant. */
export function AgendaTutorial({ onSkip, onNever, onSetup }: { onSkip: () => void; onNever: () => void; onSetup: () => void }) {
  const list = steps(!!nativeAgenda());
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
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Tutoriel de l’agenda" testID="agenda-tutorial">
          <SheetTop onClose={onSkip} label="Passer le tutoriel" />
          <ScrollView ref={scroller} contentContainerStyle={{ gap: 14 }}>
            <View key={step.key} style={[{ gap: 14 }, enter('rise')]} testID={`tutorial-step-${i + 1}`}>
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
            {last ? (
              <View style={{ gap: 8 }}>
                <Button label="⚙️ Configurer mon agenda en 3 étapes" onPress={onSetup} />
                <Button label="Plus tard" variant="secondary" onPress={onSkip} />
              </View>
            ) : (
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {i ? <Button label="‹ Retour" variant="secondary" style={{ flex: 1 }} onPress={() => setI(i - 1)} />
                  : <Button label="Passer" variant="secondary" style={{ flex: 1 }} onPress={onSkip} />}
                <Button label="Suivant" style={{ flex: 2 }} onPress={() => setI(i + 1)} />
              </View>
            )}
            <Pressable accessibilityRole="button" onPress={onNever} style={({ pressed }) => [st.never2, pressTransition, pressed && { opacity: 0.7 }]}>
              <T size={14} weight="semibold" color={colors.muted}>Ne plus me le rappeler</T>
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

// ───────────── Assistant « Configurer mon agenda en 3 étapes » ─────────────

export type SetupState = { linked: boolean; shared: SharingGroup[] };

/** Où en est la configuration : un agenda relié (iPhone autorisé ou agenda avec un lien) et les groupes partagés. */
export async function loadSetup(): Promise<SetupState> {
  const [calendars, sharing, access] = await Promise.all([
    rpc<Calendar[]>('agenda_calendars_list'),
    rpc<Sharing>('agenda_sharing'),
    nativeAccess(),
  ]);
  return { linked: access === 'full' || calendars.some((c) => c.kind === 'ics'), shared: sharing.groups.filter((g) => g.shared) };
}

/** Les adresses des étapes (les écrans existants, avec `setup=1`). */
export function setupHref(step: 1 | 2 | 3): Href {
  if (step === 1) return (nativeAgenda() ? '/agenda/calendars?iphone=1&setup=1' : '/agenda/calendars?add=1&setup=1') as Href;
  if (step === 2) return '/agenda/share?setup=1' as Href;
  return '/agenda/setup' as Href;
}

const SETUP_TITLES = { 1: 'Relie tes agendas', 2: 'Choisis tes groupes', 3: 'C’est prêt' } as const;

/** Bandeau d'une étape : « Étape 2/3 », le titre, « Passer » et (facultatif) « Suivant ». */
export function SetupBar({ step, hint, next }: { step: 1 | 2 | 3; hint: string; next?: boolean }) {
  const go = () => router.replace(setupHref((step + 1) as 2 | 3));
  return (
    <View style={[st.setupBar, enter('drop')]} testID="setup-bar" accessibilityLabel={`Configuration, étape ${step} sur 3 : ${SETUP_TITLES[step]}`}>
      <Progress step={step} />
      <T size={13} weight="bold" color={colors.accentSoft}>{`ÉTAPE ${step}/3`}</T>
      <T size={18} weight="bold">{SETUP_TITLES[step]}</T>
      <T size={14} color={colors.textSoft}>{hint}</T>
      {step < 3 ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button small label="Passer cette étape" variant="secondary" style={{ flex: 1 }} onPress={go} />
          {next ? <Button small label="Suivant ›" style={{ flex: 1 }} onPress={go} /> : null}
        </View>
      ) : null}
    </View>
  );
}

export function Progress({ step }: { step: 1 | 2 | 3 }) {
  return (
    <View style={{ flexDirection: 'row', gap: 6 }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {[1, 2, 3].map((k) => <View key={k} style={[st.bar, k <= step && st.barOn]} />)}
    </View>
  );
}

/** Ligne de la petite checklist : « ✓ Agendas reliés » ou « ○ Relier mes agendas ». */
export function CheckLine({ done, label }: { done: boolean; label: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} accessibilityLabel={`${label}${done ? ', fait' : ', à faire'}`}>
      <View style={[st.tick, done && st.tickOn]}>{done ? <Text style={{ color: colors.onMint, fontSize: 12, ...font.bold }}>✓</Text> : null}</View>
      <T size={14} weight="semibold" color={done ? colors.mint : colors.textSoft}>{label}</T>
    </View>
  );
}

export function sharedLabel(n: number) {
  return n ? `Partagé avec ${n} groupe${n > 1 ? 's' : ''}` : 'Partager avec un groupe';
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.88)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: { width: '100%', maxWidth: 480, maxHeight: '92%', gap: 8, padding: 20, paddingBottom: 24, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  art: { minHeight: 132, alignItems: 'center', justifyContent: 'center', padding: 16, borderRadius: radius.lg, backgroundColor: colors.bg,
    borderWidth: 1, borderColor: colors.line },
  title: { color: colors.text, fontFamily: 'BricolageGrotesque_800ExtraBold', fontSize: 26, letterSpacing: -0.3 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, minHeight: 40, borderRadius: radius.md, backgroundColor: colors.surface },
  dot: { width: 10, height: 10, borderRadius: 5 },
  box: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  flow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  flowBox: { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface },
  busy: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(185,167,255,0.6)' },
  busyText: { color: '#fff', fontSize: 14, ...font.bold },
  never: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill, backgroundColor: colors.redDim },
  neverText: { color: colors.redSoft, fontSize: 13, textDecorationLine: 'line-through', ...font.semibold },
  cells: { flexDirection: 'row', gap: 5 },
  cell: { width: 32, height: 40, borderRadius: 9, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: 'transparent' },
  cellBest: { borderColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.6, shadowRadius: 10 },
  link: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.accent, backgroundColor: colors.accentDim },
  slot: { paddingHorizontal: 8, paddingVertical: 5, borderRadius: 8, backgroundColor: 'rgba(91,227,166,0.14)' },
  dots: { flexDirection: 'row', gap: 6, justifyContent: 'center' },
  dotNav: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.lineStrong },
  dotOn: { width: 22, backgroundColor: colors.accent },
  never2: { alignSelf: 'center', minHeight: 44, paddingHorizontal: 12, justifyContent: 'center' },
  setupBar: { gap: 6, padding: 14, borderRadius: radius.lg, borderWidth: 1.5, borderColor: 'rgba(255,79,154,0.55)', backgroundColor: '#2A1638' },
  bar: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.lineStrong },
  barOn: { backgroundColor: colors.accent },
  tick: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  tickOn: { backgroundColor: colors.mint, borderColor: colors.mint },
});
