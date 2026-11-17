import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { CreateGroupHero, EmptyGroups, GroupRow, GroupTile } from '@/components/GroupBits';
import { CLOSE, Icon } from '@/components/HomeHeader';
import { Button, ErrorText, Input, Reveal, Screen, Skeleton, T, Title } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery, useRealtime, useSignal } from '@/lib/data';
import { fetchMyGroups, groupName, type GroupColor } from '@/lib/groups';
import { duration, enter, pressTransition, transition } from '@/lib/motion';
import { roleRank } from '@/lib/roles';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

type Invitation = { id: string; group_id: string; group: string; emoji?: string; color?: GroupColor; invited_by: string | null; at: string };
type OtherGroup = { id: string; name: string; emoji: string; color: GroupColor; system_key: string | null; created_by: string | null;
  member_group_members: { user_id: string }[] };

const SEARCH = ['M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14', 'M20 20l-3.5-3.5'];
const PLUS = ['M12 5v14', 'M5 12h14'];
const BACK = ['M15 18l-6-6 6-6'];

/**
 * Groupes (nouveau graphisme du 17.11, maquette A) : une liste façon WhatsApp (dernier message, heure, non lus,
 * prochain événement), la grande carte « Crée le groupe de ta bande », un état vide qui donne envie. Chaque groupe
 * s'ouvre sur sa page (/group/<id>) : membres, événements, discussion, réglages. Les Admins du site (rang Admin) voient
 * aussi les autres groupes, dans une section repliée.
 */
export default function GroupsScreen() {
  const me = useMe();
  const { rank } = useAuth();
  // Même critère que la base (private.sees_all_groups) : la base ne renvoie les groupes des autres qu'à eux.
  const siteAdmin = rank >= roleRank('admin');
  const [showAll, setShowAll] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, reload, error: loadError } = useQuery(async () => {
    const [groups, invitations, others] = await Promise.all([
      fetchMyGroups(),
      supabase.rpc('my_group_invitations'),
      siteAdmin
        ? supabase.from('member_groups').select('id, name, emoji, color, system_key, created_by, member_group_members(user_id)').order('name')
        : Promise.resolve({ data: [] as OtherGroup[] }),
    ]);
    const mine = new Set(groups.map((g) => g.id));
    return { groups, invitations: (invitations.data ?? []) as Invitation[],
      others: ((others.data ?? []) as OtherGroup[]).filter((g) => !mine.has(g.id)) };
  }, [siteAdmin]);
  // Nouveau message, groupe rejoint ou quitté, nom ou couleur changés : la liste suit sans recharger.
  useRealtime('groups-list', [{ table: 'group_messages' }, { table: 'member_group_members', filter: `user_id=eq.${me.id}` }], reload);
  useSignal([`user:${me.id}`], reload);

  async function answer(inv: Invitation, accept: boolean) {
    setBusy(true);
    const { error: failed } = await supabase.rpc('answer_group_invitation', { inv: inv.id, accept });
    setBusy(false);
    if (failed) return setError('La réponse n’a pas été enregistrée. Réessaie.');
    setError(null);
    if (accept) router.push(`/group/${inv.group_id}`);
    else void reload();
  }

  const q = search.trim().toLocaleLowerCase('fr');
  const groups = (data?.groups ?? []).filter((g) => !q || groupName(g).toLocaleLowerCase('fr').includes(q));
  const own = (data?.groups ?? []).filter((g) => !g.system);

  return (
    <Screen edges={['top']}>
      <View style={st.head}>
        {/* Pas d'en-tête : grand titre comme la maquette ; ‹ quand on vient d'un autre écran (Réglages, Événements). */}
        {router.canGoBack() ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Retour" onPress={() => router.back()}
            style={({ pressed }) => [st.back, pressTransition, pressed && st.pressed]}>
            <Icon paths={BACK} />
          </Pressable>
        ) : null}
        <Title level={1} size={34} style={{ flex: 1 }}>Groupes</Title>
        <Pressable accessibilityRole="button" accessibilityLabel={searchOpen ? 'Fermer la recherche' : 'Chercher un groupe'}
          onPress={() => { setSearch(''); setSearchOpen(!searchOpen); }}
          style={({ pressed }) => [st.round, searchOpen && st.roundOn, pressTransition, pressed && st.pressed]}>
          <Icon paths={searchOpen ? CLOSE : SEARCH} />
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Nouveau groupe" testID="groups-new" onPress={() => router.push('/group/new')}
          style={({ pressed }) => [st.round, st.roundAccent, pressTransition, pressed && st.pressed]}>
          <Icon paths={PLUS} />
        </Pressable>
      </View>
      {searchOpen ? (
        <View style={enter('drop')}>
          <Input accessibilityLabel="Chercher un groupe" placeholder="Chercher un groupe…" value={search} onChangeText={setSearch} autoFocus />
        </View>
      ) : null}
      <ErrorText error={error ?? loadError} />

      {data?.invitations.length ? (
        <View style={{ gap: 10 }}>
          <T size={13} weight="bold" color={colors.muted} style={st.label}>INVITATIONS REÇUES</T>
          {data.invitations.map((i, n) => (
            <Reveal key={i.id} index={n} style={st.invite}>
              <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
                <GroupTile group={{ emoji: i.emoji ?? '👯', color: i.color ?? 'pink' }} size={46} />
                <View style={{ flex: 1 }}>
                  <T weight="bold" size={16}>{i.group}</T>
                  <T muted size={13}>{i.invited_by ?? 'Quelqu’un'} t’invite dans ce groupe</T>
                </View>
              </View>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button small label="Rejoindre" style={{ flex: 1 }} disabled={busy} onPress={() => void answer(i, true)} />
                <Button small variant="secondary" label="Refuser" style={{ flex: 1 }} disabled={busy} onPress={() => void answer(i, false)} />
              </View>
            </Reveal>
          ))}
        </View>
      ) : null}

      {!data && !loadError ? (
        <View style={{ gap: 10 }} accessibilityRole="progressbar" accessibilityLabel="Chargement des groupes…">
          <Skeleton height={190} radius={24} />
          {[0, 1, 2].map((i) => <Skeleton key={i} height={92} radius={radius.lg} style={{ opacity: 1 - i * 0.25 }} />)}
        </View>
      ) : null}

      {data && !own.length && !q ? <EmptyGroups /> : null}
      {data && own.length && !q ? <CreateGroupHero /> : null}

      {data && groups.length && (own.length || q) ? (
        <View style={{ gap: 10 }}>
          <T size={13} weight="bold" color={colors.muted} style={st.label}>TES GROUPES · {groups.length}</T>
          {groups.map((g, i) => <GroupRow key={g.id} group={g} index={i} />)}
        </View>
      ) : null}
      {data && !own.length && !q && groups.length ? (
        <View style={{ gap: 10 }}>
          <T size={13} weight="bold" color={colors.muted} style={st.label}>TA COMMUNAUTÉ</T>
          {groups.map((g, i) => <GroupRow key={g.id} group={g} index={i} />)}
        </View>
      ) : null}
      {data && q && !groups.length ? <T muted style={{ textAlign: 'center', padding: 16 }}>Aucun groupe ne s’appelle comme ça.</T> : null}

      {siteAdmin && data?.others.length ? (
        <View style={{ gap: 10, marginTop: 8 }}>
          <T size={13} weight="bold" color={colors.muted} style={st.label}>TOUS LES GROUPES (ADMIN)</T>
          <Button small variant="secondary"
            label={showAll ? 'Masquer les autres groupes' : `Voir les ${data.others.length} autres groupe${data.others.length > 1 ? 's' : ''}`}
            onPress={() => setShowAll(!showAll)} />
          {showAll ? <T muted size={13}>Groupes dont tu ne fais pas partie : visibles par les Admins seulement.</T> : null}
          {showAll ? data.others.map((g, i) => (
            <Reveal key={g.id} index={i}>
              <Pressable accessibilityRole="link" accessibilityLabel={`Groupe ${groupName(g)} (admin)`} onPress={() => router.push(`/group/${g.id}`)}
                style={({ pressed }) => [st.other, transition('background-color', duration.fast), pressed && { backgroundColor: colors.surface2 }]}>
                <GroupTile group={g} size={40} />
                <View style={{ flex: 1 }}>
                  <T weight="bold">{groupName(g)}</T>
                  <T muted size={13}>{g.member_group_members.length} membre{g.member_group_members.length > 1 ? 's' : ''}</T>
                </View>
                <T muted size={20}>›</T>
              </Pressable>
            </Reveal>
          )) : null}
        </View>
      ) : null}
    </Screen>
  );
}

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52 },
  round: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: 'transparent' },
  roundOn: { backgroundColor: colors.surface2, borderColor: colors.accent },
  roundAccent: { backgroundColor: colors.action, shadowColor: colors.action, shadowOpacity: 0.45, shadowRadius: 14, shadowOffset: { width: 0, height: 5 } },
  pressed: { opacity: 0.8, transform: [{ scale: 0.94 }] },
  back: { width: 36, height: 44, marginLeft: -8, alignItems: 'center', justifyContent: 'center' },
  label: { letterSpacing: 0.8 },
  invite: { gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.accentDim, borderWidth: 1, borderColor: '#5A2346' },
  other: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: radius.lg, backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.line },
});
