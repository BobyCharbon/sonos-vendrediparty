import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Badge, PillButton, TopBar } from '@/components/agenda/Bits';
import { DayStrip, DayTimeline, MonthView, WeekView } from '@/components/agenda/Views';
import { Button, ErrorText, Screen, Segmented, Skeleton, T } from '@/components/ui';
import {
  addDays, addMonths, dayKey, isoWeekNumber, loadPeriod, longDay, monthStart, monthTitle, nativeAgenda, rpc, savePrefs, shortDay, syncBusyOnOpen, useAgendaBadge,
  weekSpoken, weekStart, weekTitle, zdate, type DayKey, type Prefs, type View as AgendaView,
} from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useRealtime, useSignal } from '@/lib/data';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * Agenda (17.11, maquettes 2A–2D et 7A validées) : la semaine par défaut (jours empilés), le jour avec ses trous
 * « Libre », le mois. En-tête : « ‹ Événements » (ou « ‹ Réglages »), Calendriers, + Ajouter, « Qui est libre ? ».
 * Les soirées Party y sont d'office ; tout se relit en temps réel (signal user:<id> et liste des événements).
 */
export default function AgendaScreen() {
  const me = useMe();
  const params = useLocalSearchParams<{ from?: string; day?: string }>();
  const backLabel = params.from === 'settings' ? 'Réglages' : 'Événements';
  const backPath = params.from === 'settings' ? '/account' : '/';
  const today = dayKey(new Date());
  // Ouverture : sur la dernière vue choisie (la première fois : la semaine).
  const prefs = useQuery(() => rpc<Prefs>('agenda_prefs_get').catch((): Prefs => ({})), []);
  const [picked, setView] = useState<AgendaView | null>(null);
  const saved = prefs.data?.view && ['day', 'week', 'month'].includes(prefs.data.view) ? prefs.data.view : 'week';
  const view: AgendaView = picked ?? saved;
  const [anchor, setAnchor] = useState<DayKey>(typeof params.day === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(params.day) ? params.day : today);
  const [welcomeHidden, setWelcomeHidden] = useState(false);
  const pending = useAgendaBadge(me.id);

  // Période chargée : la semaine (vue Semaine et Jour, pour les points de la bande), ou les 6 semaines du mois.
  const [from, to] = useMemo(() => {
    if (view === 'month') { const s = weekStart(monthStart(anchor)); return [s, addDays(s, 42)]; }
    const s = weekStart(anchor);
    return [s, addDays(s, 7)];
  }, [view, anchor]);
  const { data, error, reload } = useQuery(async () => (prefs.data ? loadPeriod(zdate(from), zdate(to)) : null), [from, to, !!prefs.data]);
  useSignal([`user:${me.id}`, 'events'], reload);
  // Mes réponses aux soirées (rsvps publiée) ; mes rendez-vous se relisent au retour sur l'écran (agenda_items hors publication).
  useRealtime('agenda-rsvps', [{ table: 'rsvps', filter: `user_id=eq.${me.id}` }], reload);

  // Partage actif : les heures prises de l'iPhone (ou des agendas ajoutés avec un lien) suivent, une fois par visite.
  useEffect(() => { void syncBusyOnOpen(); }, []);
  function pick(v: AgendaView) {
    setView(v);
    void savePrefs({ view: v });
  }
  function move(step: number) {
    setAnchor((a) => (view === 'month' ? addMonths(a, step) : addDays(a, view === 'week' ? 7 * step : step)));
  }

  const ws = weekStart(anchor);
  const title = view === 'month' ? monthTitle(anchor, today) : view === 'week' ? weekTitle(ws) : shortDay(anchor);
  const away = view === 'month' ? monthStart(anchor) !== monthStart(today) : view === 'week' ? ws !== weekStart(today) : anchor !== today;
  const spoken = view === 'month' ? monthTitle(anchor, today) : view === 'week' ? weekSpoken(ws) : longDay(anchor);
  const weekEntries = data ? data.entries.filter((e) => e.end > zdate(ws) && e.start < zdate(addDays(ws, 7))) : [];
  const emptyWeek = !!data && view === 'week' && !weekEntries.length;
  const welcome = !!data && !data.prefs.welcome_seen && !welcomeHidden;
  const native = nativeAgenda();

  function closeWelcome() {
    setWelcomeHidden(true);
    void savePrefs({ welcome_seen: true });
  }

  return (
    <Screen>
      <TopBar back={backLabel} fallback={backPath}
        right={(
          <>
            <View>
              <PillButton label="Calendriers" testID="agenda-calendars" a11y={pending ? `Calendriers, ${pending} demande${pending > 1 ? 's' : ''} de rendez-vous` : 'Calendriers'}
                onPress={() => router.push('/agenda/calendars')} />
              {pending ? <Badge count={pending} style={st.cornerBadge} /> : null}
            </View>
            <PillButton label="+ Ajouter" tone="accent" a11y="Nouveau rendez-vous" testID="agenda-add"
              onPress={() => router.push(`/agenda/item?day=${view === 'week' && ws === weekStart(today) ? today : anchor}` as Href)} />
          </>
        )} />
      <View style={st.titleRow}>
        <View style={{ flexShrink: 1 }} accessibilityLiveRegion="polite" accessibilityLabel={spoken}>
          <Text role="heading" aria-level={1} style={st.title} numberOfLines={1}>
            {title}
          </Text>
          {view !== 'month' && data?.prefs.week_numbers ? <T muted size={12}>Semaine {isoWeekNumber(ws)}</T> : null}
        </View>
        <PillButton label="👥 Qui est libre ?" tone="mint" testID="agenda-free" onPress={() => router.push('/agenda/free')} />
      </View>
      <Segmented<AgendaView> value={view} onChange={pick}
        options={[{ key: 'day', label: 'Jour' }, { key: 'week', label: 'Semaine' }, { key: 'month', label: 'Mois' }]} />
      <View style={st.nav}>
        <NavArrow dir={-1} label={view === 'month' ? 'Mois précédent' : view === 'week' ? 'Semaine précédente' : 'Jour précédent'} onPress={() => move(-1)} />
        {away ? (
          <Pressable accessibilityRole="button" onPress={() => setAnchor(today)} style={({ pressed }) => [st.today, enter('pop'), pressTransition, pressed && { opacity: 0.8 }]}>
            <Text style={{ color: colors.text, fontSize: 14, ...font.semibold }}>Aujourd’hui</Text>
          </Pressable>
        ) : <View />}
        <NavArrow dir={1} label={view === 'month' ? 'Mois suivant' : view === 'week' ? 'Semaine suivante' : 'Jour suivant'} onPress={() => move(1)} />
      </View>

      <ErrorText error={error} />
      {error ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}

      {welcome ? (
        <View style={[st.welcome, enter('rise')]} testID="agenda-welcome">
          <T size={20} weight="bold">👋 Bienvenue dans ton agenda</T>
          <T size={15} color={colors.textSoft}>Tes soirées Party y sont déjà. Ajoute tes rendez-vous avec « + Ajouter ».</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {native ? (
              <Button label="📱 Voir mon iPhone" style={{ flex: 1 }} onPress={() => { closeWelcome(); router.push('/agenda/calendars?iphone=1'); }} />
            ) : (
              <Button label="🔗 Ajouter un agenda" style={{ flex: 1 }} onPress={() => { closeWelcome(); router.push('/agenda/calendars?add=1'); }} />
            )}
            <Button label="Plus tard" variant="secondary" onPress={closeWelcome} />
          </View>
        </View>
      ) : null}

      {!data && !error ? (
        <View style={{ gap: 12 }} accessibilityRole="progressbar" accessibilityLabel="Chargement de l’agenda…">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} height={64} radius={radius.lg} style={{ opacity: 1 - i * 0.2 }} />)}
        </View>
      ) : null}

      {data && view === 'week' ? <WeekView start={ws} entries={data.entries} today={today} empty={emptyWeek} /> : null}
      {data && view === 'day' ? (
        <View style={{ gap: 12 }}>
          <DayStrip selected={anchor} entries={data.entries} today={today} onPick={setAnchor} />
          <DayTimeline day={anchor} entries={data.entries} today={today} />
        </View>
      ) : null}
      {data && view === 'month' ? (
        <MonthView month={monthStart(anchor)} entries={data.entries} today={today} selected={anchor} onPick={setAnchor} />
      ) : null}

      {emptyWeek ? (
        <View style={[st.emptyCard, enter('fade')]}>
          <T size={16} weight="bold">Rien cette semaine.</T>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            <Button small variant="secondary" label="🎉 Voir les soirées" onPress={() => router.navigate('/')} />
            <Button small label="+ Ajouter un rendez-vous" onPress={() => router.push(`/agenda/item?day=${anchor}` as Href)} />
          </View>
        </View>
      ) : null}
    </Screen>
  );
}

function NavArrow({ dir, label, onPress }: { dir: -1 | 1; label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [st.arrow, pressTransition, pressed && { opacity: 0.7, transform: [{ scale: 0.94 }] }]}>
      <View style={[st.chev, dir > 0 && { transform: [{ rotate: '225deg' }], marginLeft: -4, marginRight: 0 }]} />
    </Pressable>
  );
}

const st = StyleSheet.create({
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' },
  title: { color: colors.text, fontFamily: 'BricolageGrotesque_800ExtraBold', fontSize: 32, letterSpacing: -0.4 },
  cornerBadge: { position: 'absolute', top: -6, right: -6 },
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: -4 },
  arrow: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface },
  chev: { width: 11, height: 11, borderLeftWidth: 2.5, borderBottomWidth: 2.5, borderColor: colors.text, transform: [{ rotate: '45deg' }], marginLeft: 4 },
  today: { minHeight: 40, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: colors.surface2, justifyContent: 'center' },
  welcome: { gap: 10, padding: 16, borderRadius: radius.lg, borderWidth: 1.5, borderColor: 'rgba(255,79,154,0.55)', backgroundColor: '#2C1840',
    shadowColor: colors.accent, shadowOpacity: 0.3, shadowRadius: 20 },
  emptyCard: { gap: 10, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
});
