import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { EventCard } from '@/components/EventCard';
import { FaceStack, FloatingEmojis, GroupTile, UnreadBadge } from '@/components/GroupBits';
import { Icon } from '@/components/HomeHeader';
import { Avatar, Button, ErrorText, Loading, Reveal, T } from '@/components/ui';
import { usePersonText } from '@/components/PersonName';
import { useAuth, useMe } from '@/lib/auth';
import { fetchEventList, fetchTaxonomy, useQuery, useRealtime, useSignal } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { createdLine, plural } from '@/lib/format';
import { coverGradient, fetchGroupEventIds, fetchMyGroups, groupName, palette, type GroupColor } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';
import { openGroupChat } from '@/lib/nativeChat';
import { roleRank } from '@/lib/roles';
import { must, supabase } from '@/lib/supabase';
import { colors, font, radius } from '@/lib/theme';

type Row = { id: string; name: string; emoji: string; color: GroupColor; created_by: string | null; created_at: string;
  system_key: string | null; member_group_members: { user_id: string; added_at: string | null }[] };
type Person = { id: string; display_name: string; avatar_url: string | null };

const BACK = ['M15 18l-6-6 6-6'];
const GEAR = ['M12 15a3 3 0 1 0 0-6a3 3 0 1 0 0 6',
  'M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z'];
const MEMBERS_SHOWN = 12;

/**
 * Page du groupe (maquette A « D », 17.11) : couverture (dégradé de sa couleur + son emoji), membres, « Créer un
 * événement pour le groupe » (le formulaire s'ouvre avec ce groupe coché, sans prévenir le groupe), « Inviter »,
 * « Discussion », prochains événements (seulement ceux que je peux voir : group_events), membres ; ⚙ ouvre les réglages
 * (Modifier, lien, quitter…). Réservée aux membres (et aux Admins du site) : la base ne renvoie le groupe qu'à eux.
 */
export default function GroupPage() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const me = useMe();
  const { can, rank } = useAuth();
  const insets = useSafeAreaInsets();
  const personText = usePersonText();
  const [allMembers, setAllMembers] = useState(false);
  const [showPast, setShowPast] = useState(false);

  const { data, error, loading, reload } = useQuery(async () => {
    const [mine, row, eventIds, taxonomy] = await Promise.all([
      fetchMyGroups(),
      supabase.from('member_groups').select('id, name, emoji, color, created_by, created_at, system_key, member_group_members(user_id, added_at)')
        .eq('id', id).maybeSingle(),
      fetchGroupEventIds(id),
      fetchTaxonomy(),
    ]);
    const group = must(row) as Row | null;
    if (!group) return null;
    const ids = group.member_group_members.map((m) => m.user_id);
    const [people, events] = await Promise.all([
      ids.length ? supabase.from('profiles').select('id, display_name, avatar_url').in('id', ids) : Promise.resolve({ data: [] }),
      fetchEventList(eventIds.map((e) => e.id)),
    ]);
    const upcoming = new Set(eventIds.filter((e) => e.upcoming).map((e) => e.id));
    const order = new Map(eventIds.map((e, i) => [e.id, i]));
    const sorted = events.sort((a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));
    return { group, overview: mine.find((g) => g.id === id) ?? null, people: (people.data ?? []) as Person[],
      upcoming: sorted.filter((e) => upcoming.has(e.id)), past: sorted.filter((e) => !upcoming.has(e.id)),
      tagsById: new Map(taxonomy.tags.map((t) => [t.id, t])), loadedAt: Date.now() };
  }, [id]);
  // Membre arrivé ou parti, événement ajouté au groupe, nom ou couleur changés : la page suit.
  useRealtime(`group-${id}`, [{ table: 'member_group_members', filter: `group_id=eq.${id}` }, { table: 'event_groups', filter: `group_id=eq.${id}` },
    { table: 'group_messages', filter: `group_id=eq.${id}` }], reload);
  useSignal(['events', `user:${me.id}`], reload);

  const people = useMemo(() => new Map((data?.people ?? []).map((p) => [p.id, p])), [data?.people]);

  if (loading && !data) return <Loading />;
  if (!data) return <Gone error={error} />;

  const { group, overview } = data;
  const system = !!group.system_key;
  const memberIds = group.member_group_members.map((m) => m.user_id);
  const member = memberIds.includes(me.id);
  const manage = overview?.manage ?? (!system && (group.created_by === me.id || rank >= roleRank('admin')));
  const p = palette(group.color);
  const name = groupName(group);
  const creator = group.created_by ? people.get(group.created_by) : null;
  // Créateur d'abord, puis par surnom.
  const members = memberIds.map((uid) => people.get(uid)).filter((m): m is Person => !!m)
    .sort((a, b) => Number(b.id === group.created_by) - Number(a.id === group.created_by) || a.display_name.localeCompare(b.display_name, 'fr'));
  const faces = members.filter((m) => m.id !== me.id).slice(0, 5).map((m) => ({ id: m.id, name: m.display_name, avatar_url: m.avatar_url }));
  const canCreate = member && can('events.create');
  const back = () => (router.canGoBack() ? router.back() : router.replace('/groups'));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Stack.Screen options={{ headerShown: false, title: name }} />
      <ScrollView contentContainerStyle={{ paddingBottom: 48 }} testID="group-page">
        {/* Couverture : dégradé de la couleur du groupe, son emoji en motif qui flotte doucement. */}
        <View style={[st.cover, coverGradient(group.color), { paddingTop: insets.top + 8 }]}>
          <FloatingEmojis items={[
            { emoji: group.emoji, top: insets.top + 30, left: '38%', size: 22, opacity: 0.22 },
            { emoji: group.emoji, top: insets.top + 74, left: '66%', size: 26, opacity: 0.2, delay: 700 },
            { emoji: group.emoji, top: insets.top + 120, left: '22%', size: 20, opacity: 0.18, delay: 1300 },
            { emoji: group.emoji, top: insets.top + 150, right: 28, size: 24, opacity: 0.2, delay: 400 },
          ]} />
          <View style={st.coverBar}>
            <Pressable accessibilityRole="button" accessibilityLabel="Retour" onPress={back}
              style={({ pressed }) => [st.coverBtn, pressTransition, pressed && st.pressed]}>
              <Icon paths={BACK} />
            </Pressable>
            {member || manage ? (
              <Pressable accessibilityRole="button" accessibilityLabel="Réglages du groupe" testID="group-settings"
                onPress={() => router.push(`/group/${id}/settings`)}
                style={({ pressed }) => [st.coverBtn, pressTransition, pressed && st.pressed]}>
                <Icon paths={GEAR} />
              </Pressable>
            ) : null}
          </View>
        </View>

        <View style={st.body}>
          <View style={[st.tileWrap, enter('pop')]}><GroupTile group={group} size={84} /></View>
          <Text role="heading" aria-level={1} style={st.name}>{name}</Text>
          <View style={st.metaRow}>
            {faces.length ? <FaceStack faces={faces} total={Math.max(members.length - (member ? 1 : 0), faces.length)} size={28} /> : null}
            <T size={14} color={colors.textSoft} style={{ flex: 1 }}>
              {system ? `Toute la communauté · ${plural(memberIds.length, 'membre')}`
                : `${plural(memberIds.length, 'membre')}${creator ? ` · créé par ${group.created_by === me.id ? 'toi' : personText(creator.id, creator.display_name)}` : ''}`}
            </T>
          </View>

          {canCreate ? (
            <Reveal index={1}>
              <Pressable accessibilityRole="button" accessibilityLabel="Créer un événement pour le groupe" testID="group-create-event"
                onPress={() => router.push({ pathname: '/event/new', params: { group: id } })}
                style={({ pressed }) => [st.primary, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
                <T size={16} weight="bold" color={colors.onAction}>📅  Créer un événement pour le groupe</T>
              </Pressable>
            </Reveal>
          ) : null}
          {(manage && !system) || (member && discussionsOn) ? (
            <Reveal index={2} style={{ flexDirection: 'row', gap: 10 }}>
              {manage && !system ? (
                <Pressable accessibilityRole="button" accessibilityLabel="Inviter" testID="group-invite"
                  onPress={() => router.push(`/group/${id}/invite`)}
                  style={({ pressed }) => [st.secondary, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                  <T size={15} weight="bold">👋  Inviter</T>
                </Pressable>
              ) : null}
              {member && discussionsOn ? (
                <Pressable accessibilityRole="button" accessibilityLabel={`Discussion${overview?.unread ? `, ${overview.unread} non lus` : ''}`}
                  testID="group-chat" onPress={() => openGroupChat(id, (path) => router.push(path as never))}
                  style={({ pressed }) => [st.secondary, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                  <T size={15} weight="bold">💬  Discussion</T>
                  <UnreadBadge count={overview?.unread ?? 0} />
                </Pressable>
              ) : null}
            </Reveal>
          ) : null}

          <View style={st.sectionHead}>
            <T size={13} weight="bold" color={colors.muted} style={st.label}>PROCHAINS ÉVÉNEMENTS</T>
            {data.upcoming.length ? <T size={13} weight="bold" color={p.text}>{data.upcoming.length}</T> : null}
          </View>
          {data.upcoming.length ? data.upcoming.map((e, i) => (
            <EventCard key={e.id} index={i} event={e} me={me.id} tagsById={data.tagsById} onChanged={reload} quickRsvp now={data.loadedAt} />
          )) : (
            <Reveal style={[st.empty, { borderColor: `${p.main}55` }]}>
              <Text style={{ fontSize: 30 }}>{group.emoji}</Text>
              <T weight="bold" style={{ textAlign: 'center' }}>Aucun événement prévu</T>
              <T muted size={13} style={{ textAlign: 'center' }}>
                {canCreate ? 'Lance la prochaine : le groupe sera déjà coché, tu choisis ensuite de le prévenir.' : 'Les événements du groupe apparaîtront ici.'}
              </T>
            </Reveal>
          )}
          {data.past.length ? (
            <Button small variant="ghost" label={showPast ? 'Masquer les événements passés' : `Voir ${plural(data.past.length, 'événement passé', 'événements passés')}`}
              onPress={() => setShowPast(!showPast)} />
          ) : null}
          {showPast ? data.past.map((e, i) => (
            <EventCard key={e.id} index={i} event={e} me={me.id} tagsById={data.tagsById} onChanged={reload} now={data.loadedAt} />
          )) : null}

          <View style={st.sectionHead}>
            <T size={13} weight="bold" color={colors.muted} style={st.label}>MEMBRES · {memberIds.length}</T>
          </View>
          <View style={st.members}>
            {(allMembers ? members : members.slice(0, MEMBERS_SHOWN)).map((m, i) => (
              <View key={m.id} style={[st.member, i ? st.memberLine : null]}>
                <Avatar id={m.id} name={m.display_name} photo={m.avatar_url} size={40} />
                <T weight="semibold" numberOfLines={1} style={{ flex: 1 }}>{m.id === me.id ? `${personText(m.id, m.display_name)} (toi)` : personText(m.id, m.display_name)}</T>
                {m.id === group.created_by ? <T size={12} weight="bold" color={p.text}>Créateur</T> : null}
              </View>
            ))}
          </View>
          {members.length > MEMBERS_SHOWN ? (
            <Button small variant="ghost" label={allMembers ? 'Moins de membres' : `Voir les ${members.length} membres`} onPress={() => setAllMembers(!allMembers)} />
          ) : null}
          <T muted size={12} style={{ textAlign: 'center' }}>{createdLine(false, group.created_at, null).replace('Événement', 'Groupe')}</T>
        </View>
      </ScrollView>
    </View>
  );
}

function Gone({ error }: { error?: string | null }) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: 24, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Groupe' }} />
      <T weight="bold" size={20}>Groupe introuvable</T>
      <T muted>Ce groupe n’existe plus, ou tu n’en fais pas partie.</T>
      <ErrorText error={error ?? null} />
      <Button label="Mes groupes" onPress={() => router.replace('/groups')} />
    </View>
  );
}

const st = StyleSheet.create({
  cover: { height: 236, paddingHorizontal: 16, overflow: 'hidden' },
  coverBar: { flexDirection: 'row', justifyContent: 'space-between' },
  coverBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(21,16,42,0.45)', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)' },
  pressed: { opacity: 0.8, transform: [{ scale: 0.92 }] },
  body: { paddingHorizontal: 16, gap: 12, marginTop: -60, width: '100%', maxWidth: 640, alignSelf: 'center' },
  tileWrap: { alignSelf: 'flex-start', borderRadius: 28, borderWidth: 4, borderColor: colors.bg },
  name: { color: colors.text, fontSize: 32, lineHeight: 36, ...font.display, letterSpacing: -0.6 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  primary: { minHeight: 52, borderRadius: radius.md, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center', marginTop: 4,
    shadowColor: colors.action, shadowOpacity: 0.45, shadowRadius: 18, shadowOffset: { width: 0, height: 6 } },
  secondary: { flex: 1, flexDirection: 'row', gap: 8, minHeight: 50, borderRadius: radius.md, backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 14 },
  label: { letterSpacing: 0.8 },
  empty: { alignItems: 'center', gap: 6, padding: 20, borderRadius: radius.lg, borderWidth: 1, borderStyle: 'dashed', backgroundColor: colors.surface },
  members: { borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12 },
  member: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 58 },
  memberLine: { borderTopWidth: 1, borderTopColor: colors.line },
});
