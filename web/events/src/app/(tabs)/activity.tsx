import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Chip, Empty, ErrorText, Reveal, Screen, T, Title } from '@/components/ui';
import { Announcements } from '@/components/Announcements';
import { GroupRequests } from '@/components/GroupRequests';
import { BADGE_RED, HIDDEN_KIND, isImportant } from '@/lib/activityBadge';
import { useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { duration, pressTransition, transition } from '@/lib/motion';
import { must, supabase } from '@/lib/supabase';
import { colors, font, radius } from '@/lib/theme';

type Item = { id: string; kind: string; title: string; body: string; event_id: string | null; created_at: string; read_at: string | null };
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
    const res = await supabase
      .from('notifications')
      .select('id, kind, title, body, event_id, created_at, read_at')
      .neq('kind', HIDDEN_KIND)
      .order('created_at', { ascending: false })
      .limit(100);
    return must(res) as Item[];
  }, [me.id]);
  // null = choix automatique : « Importantes » s'il y en a de non lues, sinon « Tout ».
  const [picked, setPicked] = useState<Filter | null>(null);

  async function open(n: Item) {
    if (!n.read_at) await supabase.from('notifications').update({ read_at: new Date().toISOString() }).eq('id', n.id);
    if (n.event_id) router.push(`/event/${n.event_id}`);
    else reload();
  }

  async function markAll() {
    await supabase.from('notifications').update({ read_at: new Date().toISOString() }).is('read_at', null);
    reload();
  }

  const unread = data?.filter((n) => !n.read_at).length ?? 0;
  const importantUnread = data?.filter((n) => !n.read_at && isImportant(n.kind)).length ?? 0;
  const filter: Filter = picked ?? (importantUnread > 0 ? 'important' : 'all');
  const list = (data ?? []).filter((n) => filter === 'all' || isImportant(n.kind));
  const fresh = list.filter((n) => !n.read_at);
  const seen = list.filter((n) => n.read_at);

  return (
    <Screen edges={[]}>
      <View style={st.header}>
        <Title level={1} style={{ flex: 1 }}>Activité</Title>
        {unread ? <Button small variant="ghost" label="Tout marquer lu" onPress={markAll} /> : null}
        <Pressable accessibilityRole="button" accessibilityLabel="Fermer l'activité" onPress={close}
          style={({ pressed }) => [st.close, pressed && { opacity: 0.6 }]}>
          <Text style={st.closeText}>✕</Text>
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
      {fresh.map((n, i) => <Row key={n.id} n={n} index={i} onPress={() => open(n)} />)}
      {fresh.length && seen.length ? <T size={12} weight="bold" color={colors.muted} style={st.section}>DÉJÀ LU</T> : null}
      {seen.map((n, i) => <Row key={n.id} n={n} index={fresh.length + i} onPress={() => open(n)} />)}
      <T muted size={12} style={st.note}>
        « Importantes » : invitations, sondages, dates fixées, changements et annulations. La bulle rouge de la cloche ne compte qu’elles.
      </T>
    </Screen>
  );
}

function Row({ n, index, onPress }: { n: Item; index: number; onPress: () => void }) {
  const hot = !n.read_at && isImportant(n.kind);
  return (
    <Reveal index={index}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${n.read_at ? '' : 'Non lu : '}${n.title}. ${n.body}`}
        onPress={onPress}
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
    </Reveal>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center' },
  closeText: { color: colors.textSoft, fontSize: 18, lineHeight: 20, ...font.semibold },
  filters: { flexDirection: 'row', gap: 6 },
  section: { letterSpacing: 0.6, marginTop: 6 },
  note: { textAlign: 'center', marginTop: 8 },
  row: { flexDirection: 'row', gap: 12, padding: 14, borderRadius: radius.md, borderWidth: 1, borderColor: 'transparent', backgroundColor: 'transparent' },
  rowUnread: { backgroundColor: colors.surface },
  rowHot: { backgroundColor: '#2A1C3A', borderColor: '#5A2346' },
  pressed: { opacity: 0.8, transform: [{ scale: 0.98 }] },
  dot: { width: 8, height: 8, borderRadius: 4, marginTop: 7, backgroundColor: 'transparent' },
});
