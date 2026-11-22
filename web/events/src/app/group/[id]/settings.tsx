import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { ColorPicker, EmojiPicker, GroupTile } from '@/components/GroupBits';
import { GroupEventRules } from '@/components/GroupEventRules';
import { GroupPhotoField } from '@/components/GroupPhotoField';
import { InviteLinkCard } from '@/components/InviteLinkCard';
import { usePersonText } from '@/components/PersonName';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ConfirmButton, ErrorText, Input, Loading, Screen, Section, T, Toast, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { GROUP_COLOR_KEYS, GROUP_PHOTOS, groupName, saveGroupPhoto, type GroupColor } from '@/lib/groups';
import { dbMessage } from '@/lib/moderation';
import { roleRank } from '@/lib/roles';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

type Row = { id: string; name: string; emoji: string; color: GroupColor; photo_path: string | null; created_by: string | null; system_key: string | null;
  events_need_approval: boolean; announce_mode: 'request' | 'free'; members_invite: boolean; member_group_members: { user_id: string }[] };

/**
 * Réglages du groupe (⚙ de sa page) : ce qui était dans Réglages › Groupes, inchangé côté droits — Modifier (nom, emoji,
 * couleur : son créateur ou un Admin du site), montrer mon numéro, règles des événements, membres (retirer), autres
 * liens d'invitation, supprimer ; quitter soi-même (jamais Membres Vendredi Party, ni le créateur).
 */
export default function GroupSettings() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const me = useMe();
  const { rank } = useAuth();
  const personText = usePersonText();
  const terms = useTermsGate();
  const [draft, setDraft] = useState<{ name: string; emoji: string; color: GroupColor } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const { data, loading, error: loadError, reload } = useQuery(async () => {
    const [row, privacy] = await Promise.all([
      supabase.from('member_groups').select('id, name, emoji, color, photo_path, created_by, system_key, events_need_approval, announce_mode, members_invite, member_group_members(user_id)')
        .eq('id', id).maybeSingle(),
      supabase.rpc('my_privacy'),
    ]);
    const group = must(row) as Row | null;
    if (!group) return null;
    const ids = group.member_group_members.map((m) => m.user_id);
    const people = ids.length ? await supabase.from('profiles').select('id, display_name, avatar_url').in('id', ids) : { data: [] };
    return { group, people: (people.data ?? []) as { id: string; display_name: string; avatar_url: string | null }[],
      phoneGroups: new Set(((privacy.data as { phone_groups?: string[] } | null)?.phone_groups) ?? []) };
  }, [id]);

  if (loading && !data) return <Loading />;
  if (!data) return <Screen edges={[]}><ErrorText error={loadError ?? 'Ce groupe n’existe plus, ou tu n’en fais pas partie.'} /></Screen>;

  const { group } = data;
  const system = !!group.system_key;
  const member = group.member_group_members.some((m) => m.user_id === me.id);
  const manage = !system && (group.created_by === me.id || rank >= roleRank('admin'));
  const look = draft ?? { name: group.name, emoji: group.emoji, color: group.color };
  const changed = !!draft && (draft.name.trim() !== group.name || draft.emoji !== group.emoji || draft.color !== group.color);

  async function run(p: PromiseLike<{ error: { message: string } | null }>, ok?: string) {
    setBusy(true);
    const { error: failed } = await p;
    setBusy(false);
    setError(failed ? 'La modification n’a pas été enregistrée. Réessaie.' : null);
    if (!failed && ok) setNote(ok);
    await reload();
    return !failed;
  }

  async function saveLook() {
    if (!draft || !draft.name.trim()) return;
    if (!(await terms.ensure())) return;  // le nom d'un groupe est un contenu (CGU, filtre de la base)
    setBusy(true);
    const { error: failed } = await supabase.from('member_groups').update({ name: draft.name.trim(), emoji: draft.emoji, color: draft.color }).eq('id', group.id);
    setBusy(false);
    if (failed) return setError(dbMessage(failed.message, 'Le groupe n’a pas été modifié. Réessaie.'));
    setError(null);
    setDraft(null);
    setNote('Groupe enregistré');
    void reload();
  }

  async function changePhoto(uri: string | null) {
    if (uri && !(await terms.ensure())) return;  // une photo est un contenu (CGU)
    setBusy(true);
    try {
      await saveGroupPhoto(group.id, uri, group.photo_path);
      setError(null);
      setNote(uri ? 'Photo enregistrée' : 'Photo retirée');
    } catch (e) {
      setError(e instanceof Error && !('code' in e) ? e.message : dbMessage((e as { message?: string }).message, 'La photo n’a pas été enregistrée. Réessaie.'));
    }
    setBusy(false);
    void reload();
  }

  return (
    <Screen edges={[]}>
      {terms.sheet}
      <Stack.Screen options={{ title: 'Réglages du groupe' }} />
      <ErrorText error={error} />

      {manage ? (
        <Section title="Modifier le groupe">
          <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
            <GroupTile group={{ ...look, photo_path: group.photo_path }} size={56} />
            <Input accessibilityLabel="Nom du groupe" value={look.name} maxLength={60} style={{ flex: 1 }}
              onChangeText={(name) => setDraft({ ...look, name })} />
          </View>
          <T size={14} weight="semibold" color={colors.textSoft}>Un emoji</T>
          <EmojiPicker value={look.emoji} onChange={(emoji) => setDraft({ ...look, emoji })} />
          <T size={14} weight="semibold" color={colors.textSoft}>Une couleur</T>
          <ColorPicker value={look.color} onChange={(c) => setDraft({ ...look, color: c as GroupColor })} colorsList={GROUP_COLOR_KEYS} />
          <Button label="Enregistrer" disabled={!changed || !look.name.trim()} loading={busy} onPress={() => void saveLook()} />
          <GroupPhotoField has={!!group.photo_path} disabled={busy} onPicked={(uri) => void changePhoto(uri)}
            onRemove={() => void changePhoto(null)} />
        </Section>
      ) : (
        <Section title={groupName(group)}>
          <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
            <GroupTile group={group} size={56} />
            <T muted size={13} style={{ flex: 1 }}>{system
              ? 'Tous les Membres VIP et au-dessus, tenu à jour tout seul : passer quelqu’un Membre VIP l’ajoute, le remettre Guest le retire (Administration → Membres).'
              : 'Seul le créateur du groupe change son nom, son emoji, sa couleur et sa photo.'}</T>
          </View>
        </Section>
      )}

      {member ? (
        <Section title="Ma confidentialité">
          <ToggleRow label="Montrer mon numéro dans ce groupe" hint="Les membres de ce groupe le voient sur ta fiche profil. Caché par défaut."
            value={data.phoneGroups.has(group.id)} disabled={busy}
            onChange={(visible) => void run(supabase.rpc('set_group_phone_share', { grp: group.id, visible }))} />
        </Section>
      ) : null}

      {/* Règles du groupe : « Tous les membres peuvent inviter » (avis f0e9bf158133, 22.11, allumé par défaut ; qui gère le
          groupe, jamais Membres Vendredi Party ; éteint : seuls ceux qui gèrent invitent et partagent son lien), puis les
          réglages des événements (06.11 ; « Événements à valider » éteint par défaut ; Vendredi Party : Co-admins et plus). */}
      {(system && rank >= roleRank('coadmin')) || manage ? (
        <Section title="Règles du groupe">
          {manage ? (
            <ToggleRow label="Tous les membres peuvent inviter"
              hint={group.members_invite !== false
                ? 'Chaque membre peut ajouter quelqu’un et partager le lien du groupe.'
                : 'Seuls toi et ceux qui gèrent le groupe invitent et partagent le lien du groupe.'}
              value={group.members_invite !== false} disabled={busy}
              onChange={(allowed) => void run(supabase.rpc('set_group_members_invite', { grp: group.id, allowed }),
                allowed ? 'Tous les membres peuvent inviter' : 'Seuls ceux qui gèrent le groupe invitent')} />
          ) : null}
          <GroupEventRules groupId={group.id} needApproval={!!group.events_need_approval} mode={group.announce_mode ?? 'request'} system={system}
            onSaved={() => void reload()} />
        </Section>
      ) : null}

      {manage ? (
        <Section title={`Membres · ${group.member_group_members.length}`}>
          <Button small variant="secondary" label="👋 Inviter des gens" onPress={() => router.push(`/group/${group.id}/invite`)} />
          {data.people.map((p) => (
            <View key={p.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Avatar id={p.id} name={p.display_name} photo={p.avatar_url} size={34} />
              <T style={{ flex: 1 }} numberOfLines={1}>{personText(p.id, p.display_name)}{p.id === group.created_by ? ' · Créateur' : ''}</T>
              {p.id !== group.created_by && p.id !== me.id ? (
                <ConfirmButton small label="Retirer" confirmLabel="Confirmer"
                  onConfirm={() => run(supabase.from('member_group_members').delete().eq('group_id', group.id).eq('user_id', p.id), `${p.display_name} a quitté le groupe`)} />
              ) : null}
            </View>
          ))}
        </Section>
      ) : null}

      {manage ? <InviteLinkCard kind="group" id={group.id} /> : null}

      {member && !system && group.created_by !== me.id ? (
        // Quitter soi-même (recette du 10.11) : la base le permet (politique « quitter le groupe »), jamais Vendredi Party.
        <ConfirmButton label="Quitter le groupe" confirmLabel="Confirmer : quitter le groupe"
          onConfirm={async () => {
            if (await run(supabase.from('member_group_members').delete().eq('group_id', group.id).eq('user_id', me.id).select('user_id').single())) {
              router.replace('/groups');
            }
          }} />
      ) : null}
      {manage ? (
        <View style={{ gap: 6 }}>
          <ConfirmButton label="Supprimer le groupe" confirmLabel="Confirmer la suppression"
            onConfirm={async () => {
              const photo = group.photo_path;
              if (await run(supabase.from('member_groups').delete().eq('id', group.id))) {
                if (photo) void supabase.storage.from(GROUP_PHOTOS).remove([photo]);  // la photo part avec le groupe
                router.replace('/groups');
              }
            }} />
          <T muted size={13}>Les invités qui ont déjà répondu gardent l’accès à leurs événements.</T>
        </View>
      ) : null}
      {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
    </Screen>
  );
}
