import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { PanResponder, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';

import { Button, Chip, Empty, ErrorText, Reveal, Screen, T, Title } from '@/components/ui';
import { Announcements } from '@/components/Announcements';
import { CLOSE, Icon } from '@/components/HomeHeader';
import { GroupRequests } from '@/components/GroupRequests';
import { BADGE_RED, HIDDEN_KIND, isImportant } from '@/lib/activityBadge';
import { useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { refreshPending } from '@/lib/pending';
import { duration, ease, pressTransition, transition } from '@/lib/motion';
import { storeApp } from '@/lib/features';
import { DRINK_RE } from '@/lib/storeEvents';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

type Item = { id: string; kind: string; title: string; body: string; event_id: string | null; created_at: string; read_at: string | null;
  data?: { group_id?: string; booking_id?: string } | null };
type Filter = 'important' | 'all';

/** Fermer : retour à l'accueil (ouverte depuis la cloche) ou, ouverte d'une notification, l'accueil à sa place. */
function close() {
  if (router.canGoBack()) router.back();
  else router.replace('/');
}

/** Historique des notifications reçues (les mêmes que les push), ouvert depuis la cloche de l'accueil. */
export default function Activity() {
  const me = useMe();
  const { data, error, reload } = useQuery(async () => {
    let q = supabase
      .from('notifications')
      .select('id, kind, title, body, event_id, created_at, read_at, data')
      .neq('kind', HIDDEN_KIND);
    // App App Store (refus Apple 1.4.3) : le bar y est caché, ses notifications (« 🍹 Barman… ») aussi.
    if (storeApp) q = q.not('kind', 'like', 'bar_%');
    const res = await q.order('created_at', { ascending: false }).limit(100);
    const items = must(res) as Item[];
    // Même règle que send-push : dans l'app App Store, un texte qui parle de boisson devient neutre (1.4.3).
    return storeApp ? items.map((n) => (DRINK_RE.test(`${n.title} ${n.body}`)
      ? { ...n, title: 'Party', body: 'Nouvelle activité : touche pour la voir.' } : n)) : items;
  }, [me.id]);
  // null = choix automatique : « Importantes » s'il y en a de non lues, sinon « Tout ».
  const [picked, setPicked] = useState<Filter | null>(null);
  // Lues d'un glissé (avis 85cd4af01e3e) : éteintes tout de suite, avant même la relecture.
  const [readNow, setReadNow] = useState<Record<string, string>>({});

  async function open(n: Item) {
    if (!n.read_at) await supabase.from('notifications').update({ read_at: new Date().toISOString() }).eq('id', n.id);
    refreshPending();  // pastille de l'onglet Événements
    if (n.event_id) router.push(`/event/${n.event_id}`);
    // Nouveau compte (admins, avis 662065a54b22) : la liste des inscrits, connexions récentes en haut.
    else if (n.kind === 'member_signup') router.push('/admin/users');
    // « Tu es dans le groupe X » (17.11) : la discussion du groupe, son bandeau et « Quitter ».
    else if (n.kind === 'group_added' && /^[0-9a-f-]{36}$/.test(n.data?.group_id ?? '')) router.push(`/chats/${n.data!.group_id}`);
    // Agenda (17.11) : « Nouvelle demande de rendez-vous » / « Rendez-vous annulé » ouvrent la demande.
    else if ((n.kind === 'booking_request' || n.kind === 'booking_cancelled') && /^[0-9a-f-]{36}$/.test(n.data?.booking_id ?? '')) router.push(`/agenda/requests/${n.data!.booking_id}`);
    else reload();
  }

  /** Glisser de droite à gauche : lue, sans l'ouvrir (VoiceOver : l'ouvrir la marque lue, ou « Tout marquer lu »). */
  // Stable : le glissé en cours n'est pas recréé à chaque rendu de la liste.
  const markRead = useCallback(async (n: Item) => {
    if (n.read_at) return;
    const at = new Date().toISOString();
    setReadNow((m) => ({ ...m, [n.id]: at }));
    await supabase.from('notifications').update({ read_at: at }).eq('id', n.id);
    refreshPending();
    reload();
  }, [reload]);

  async function markAll() {
    await supabase.from('notifications').update({ read_at: new Date().toISOString() }).is('read_at', null);
    refreshPending();
    reload();
  }

  const items = (data ?? []).map((n) => (n.read_at || !readNow[n.id] ? n : { ...n, read_at: readNow[n.id] }));
  const unread = items.filter((n) => !n.read_at).length;
  const importantUnread = items.filter((n) => !n.read_at && isImportant(n.kind)).length;
  const filter: Filter = picked ?? (importantUnread > 0 ? 'important' : 'all');
  const list = items.filter((n) => filter === 'all' || isImportant(n.kind));
  const fresh = list.filter((n) => !n.read_at);
  const seen = list.filter((n) => n.read_at);

  return (
    <Screen edges={[]}>
      <View style={st.header}>
        <Title level={1} style={{ flex: 1 }}>Activité</Title>
        {unread ? <Button small variant="ghost" label="Tout marquer lu" onPress={markAll} /> : null}
        <Pressable accessibilityRole="button" accessibilityLabel="Fermer l'activité" onPress={close}
          style={({ pressed }) => [st.close, pressed && { opacity: 0.6 }]}>
          <Icon paths={CLOSE} />
        </Pressable>
      </View>
      <View style={st.filters}>
        <Chip label={importantUnread ? `Importantes · ${importantUnread}` : 'Importantes'} selected={filter === 'important'} onPress={() => setPicked('important')} />
        <Chip label="Tout" selected={filter === 'all'} onPress={() => setPicked('all')} />
      </View>
      <ErrorText error={error} />
      {/* Annonces et événements à valider pour mes groupes (le toucher sur la notification ouvre cet écran). */}
      <GroupRequests refreshKey={data?.length} />
      <Announcements compact />
      {data && list.length === 0 ? (
        <Empty>{filter === 'important' ? 'Rien d’important pour l’instant : invitations, sondages et changements arriveront ici.' : 'Aucune notification pour l’instant.'}</Empty>
      ) : null}
      {/* Entrée en cascade à l’ouverture ; marquée lue, une notification s’éteint en fondu. */}
      {fresh.map((n, i) => <Row key={n.id} n={n} index={i} onPress={() => open(n)} onRead={markRead} />)}
      {fresh.length && seen.length ? <T size={12} weight="bold" color={colors.muted} style={st.section}>DÉJÀ LU</T> : null}
      {seen.map((n, i) => <Row key={n.id} n={n} index={fresh.length + i} onPress={() => open(n)} />)}
      <T muted size={12} style={st.note}>
        « Importantes » : invitations, sondages, dates fixées, changements et annulations. La bulle rouge de la cloche ne compte qu’elles.
        {fresh.length ? ' Glisse une notification vers la gauche pour la marquer comme lue.' : ''}
      </T>
    </Screen>
  );
}

const READ_AT = 80;  // px glissés vers la gauche pour « lue »

/** Une notification ; non lue, elle se glisse de droite à gauche pour la marquer comme lue (avis 85cd4af01e3e). */
function Row({ n, index, onPress, onRead }: { n: Item; index: number; onPress: () => void; onRead?: (n: Item) => void }) {
  const hot = !n.read_at && isImportant(n.kind);
  const canRead = !n.read_at && !!onRead;
  const [drag, setDrag] = useState<number | null>(null);
  // Un glissé n'est jamais aussi un toucher (le web envoie son clic après la fin du glissé).
  const [swipedAt, setSwipedAt] = useState(-1e9);
  const pan = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponderCapture: (_e, g) => canRead && g.dx < -12 && Math.abs(g.dx) > Math.abs(g.dy) * 1.6,
    onPanResponderGrant: (e) => setSwipedAt(e.timeStamp),
    onPanResponderMove: (_e, g) => setDrag(Math.max(-160, Math.min(0, g.dx))),
    onPanResponderTerminationRequest: () => false,
    onPanResponderRelease: (e, g) => {
      setSwipedAt(e.timeStamp);
      setDrag(null);
      if (g.dx < -READ_AT || (g.vx < -0.6 && g.dx < -30)) onRead?.(n);
    },
    onPanResponderTerminate: (e) => { setSwipedAt(e.timeStamp); setDrag(null); },
  }), [canRead, onRead, n]);
  const x = drag ?? 0;
  const ready = x < -READ_AT;
  return (
    <Reveal index={index}>
      <View style={st.swipe}>
        {x < 0 ? (
          <View style={[st.readSide, { backgroundColor: ready ? colors.lavender : colors.lavenderDim }, transition('background-color', duration.fast)]}>
            <T weight="bold" size={14} color={ready ? colors.onAccent : colors.lavender}>✓ Lu</T>
          </View>
        ) : null}
        <View {...(canRead ? pan.panHandlers : {})}
          style={[{ transform: [{ translateX: x }] }, canRead ? webOnly({ touchAction: 'pan-y pinch-zoom', userSelect: 'none', WebkitTouchCallout: 'none' }) : null,
            drag === null ? transition('transform', 280, ease.out) : null]}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${n.read_at ? '' : 'Non lu : '}${n.title}. ${n.body}`}
            testID={`activity-${n.id}`}
            onPress={(e) => { if (Math.abs(e.timeStamp - swipedAt) < 900) return; onPress(); }}
            style={({ pressed }) => [st.row, !n.read_at && st.rowUnread, hot && st.rowHot, pressTransition,
              transition('background-color, transform, opacity', duration.base), pressed && st.pressed]}
          >
            <View style={[st.dot, !n.read_at && { backgroundColor: hot ? BADGE_RED : colors.accent }, transition('background-color', duration.slow)]} />
            <View style={{ flex: 1, gap: 2 }}>
              <T weight="semibold">{n.title}</T>
              <T muted size={14}>{n.body}</T>
              <T muted size={12}>{formatMessageTime(n.created_at)}</T>
            </View>
          </Pressable>
        </View>
      </View>
    </Reveal>
  );
}

const webOnly = (style: Record<string, unknown>) => style as ViewStyle;

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center' },
  filters: { flexDirection: 'row', gap: 6 },
  section: { letterSpacing: 0.6, marginTop: 6 },
  note: { textAlign: 'center', marginTop: 8 },
  swipe: { position: 'relative', borderRadius: radius.md, overflow: 'hidden' },
  readSide: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, borderRadius: radius.md, alignItems: 'flex-end', justifyContent: 'center', paddingRight: 22 },
  row: { flexDirection: 'row', gap: 12, padding: 14, borderRadius: radius.md, borderWidth: 1, borderColor: 'transparent', backgroundColor: 'transparent' },
  rowUnread: { backgroundColor: colors.surface },
  rowHot: { backgroundColor: '#2A1C3A', borderColor: '#5A2346' },
  pressed: { opacity: 0.8, transform: [{ scale: 0.98 }] },
  dot: { width: 8, height: 8, borderRadius: 4, marginTop: 7, backgroundColor: 'transparent' },
});
