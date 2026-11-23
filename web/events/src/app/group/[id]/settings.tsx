import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { ColorPicker, EmojiPicker, GroupTile } from '@/components/GroupBits';
import { GroupEventRules } from '@/components/GroupEventRules';
import { GroupPhotoField } from '@/components/GroupPhotoField';
import { InviteLinkCard } from '@/components/InviteLinkCard';
import { openProfile } from '@/components/NameLinks';
import { usePersonText } from '@/components/PersonName';
import { SheetBackdrop, SheetTop, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ConfirmButton, ErrorText, Input, Loading, Screen, Section, T, Title, Toast, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import {
  loadGroupPanel, myRoleLine, RIGHT_KEYS, RIGHTS, ROLE_DETAIL, ROLE_TITLE, whoText,
  type GroupPanel, type GroupRole, type PanelMember,
} from '@/lib/groupRights';
import { GROUP_COLOR_KEYS, GROUP_PHOTOS, groupName, saveGroupPhoto, type GroupColor } from '@/lib/groups';
import { dbMessage } from '@/lib/moderation';
import { roleRank } from '@/lib/roles';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

/**
 * Réglages du groupe (⚙ de sa page), maquette du 23.11 « Réglages du groupe » : rôles dans le groupe (Admin = créateur,
 * Co-admins, Organisateurs, Membres ; toucher un membre ouvre son rôle), « Qui peut… » (un écran par droit,
 * /group/<id>/right?k=…), « Entrée dans le groupe » (accepter chaque nouveau membre, lien), puis transmettre / supprimer.
 * La base décide de tout (group_admin_panel, set_group_right, set_group_role…) ; jamais Membres Vendredi Party.
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
  const [roleOf, setRoleOf] = useState<PanelMember | null>(null);
  const [handing, setHanding] = useState(false);

  const { data, loading, error: loadError, reload } = useQuery(async () => {
    const [panel, privacy] = await Promise.all([
      loadGroupPanel(id, me.id, rank >= roleRank('admin')),
      supabase.rpc('my_privacy'),
    ]);
    if (!panel) return null;
    return { panel, phoneGroups: new Set(((privacy.data as { phone_groups?: string[] } | null)?.phone_groups) ?? []) };
  }, [id]);

  if (loading && !data) return <Loading />;
  if (!data) return <Screen edges={[]}><ErrorText error={loadError ?? 'Ce groupe n’existe plus, ou tu n’en fais pas partie.'} /></Screen>;

  const p: GroupPanel = data.panel;
  const group = p.group;
  const system = group.system;
  const mine = p.me;
  const member = mine.role !== null;
  const manage = !system && mine.manage;
  const look = draft ?? { name: group.name, emoji: group.emoji, color: group.color as GroupColor };
  const changed = !!draft && (draft.name.trim() !== group.name || draft.emoji !== group.emoji || draft.color !== group.color);
  const byRole = (r: GroupRole) => p.members.filter((m) => m.role === r);

  async function run(call: PromiseLike<{ error: { message: string } | null }>, ok?: string, fallback = 'La modification n’a pas été enregistrée. Réessaie.') {
    setBusy(true);
    const { error: failed } = await call;
    setBusy(false);
    setError(failed ? dbMessage(failed.message, fallback) : null);
    if (!failed && ok) setNote(ok);
    await reload();
    return !failed;
  }

  async function saveLook() {
    if (!draft || !draft.name.trim()) return;
    if (!(await terms.ensure())) return;  // le nom d'un groupe est un contenu (CGU, filtre de la base)
    const call = p.legacy
      ? supabase.from('member_groups').update({ name: draft.name.trim(), emoji: draft.emoji, color: draft.color }).eq('id', group.id)
      : supabase.rpc('update_group_look', { grp: group.id, group_name: draft.name.trim(), group_emoji: draft.emoji, group_color: draft.color });
    if (await run(call, 'Groupe enregistré', 'Le groupe n’a pas été modifié. Réessaie.')) setDraft(null);
  }

  async function changePhoto(uri: string | null) {
    if (uri && !(await terms.ensure())) return;  // une photo est un contenu (CGU)
    setBusy(true);
    try {
      await saveGroupPhoto(group.id, uri, group.photo);
      setError(null);
      setNote(uri ? 'Photo enregistrée' : 'Photo retirée');
    } catch (e) {
      setError(e instanceof Error && !('code' in e) ? e.message : dbMessage((e as { message?: string }).message, 'La photo n’a pas été enregistrée. Réessaie.'));
    }
    setBusy(false);
    void reload();
  }

  const names = (list: PanelMember[]) => list.map((m) => (m.id === me.id ? 'Toi' : personText(m.id, m.name))).join(', ');
  const creator = byRole('creator')[0];
  const roleRows: { key: string; short: string; tint: string; name: string; who: string }[] = [
    { key: 'creator', short: 'A', tint: colors.accentSoft, name: 'Admin du groupe',
      who: creator ? (creator.id === me.id ? 'Toi (créateur)' : `${personText(creator.id, creator.name)} (créateur)`) : 'Personne' },
    { key: 'coadmin', short: 'CO', tint: colors.lavender, name: 'Co-admins',
      who: byRole('coadmin').length ? `${names(byRole('coadmin'))} · tous les droits sauf supprimer le groupe` : 'Personne pour l’instant' },
    { key: 'organizer', short: 'OR', tint: colors.coral, name: 'Organisateurs',
      who: byRole('organizer').length ? `${names(byRole('organizer'))} · événements et annonces` : 'Personne pour l’instant' },
    { key: 'member', short: 'M', tint: colors.mint, name: 'Membres',
      who: byRole('member').length === 1 ? '1 personne' : `${byRole('member').length} personnes` },
  ];
  // Qui je peux toucher dans la liste : qui gère (sauf le créateur et moi), ou « Retirer un membre » (simples membres).
  const touchable = (m: PanelMember) => m.id !== me.id && m.role !== 'creator' && (manage || (mine.remove && m.role === 'member'));
  const editLine = p.rights.edit === 'staff'
    ? 'Seuls les organisateurs et les admins du groupe changent son nom, son emoji, sa couleur et sa photo.'
    : 'Seuls l’admin et les co-admins du groupe changent son nom, son emoji, sa couleur et sa photo.';

  return (
    <Screen edges={[]}>
      {terms.sheet}
      <Stack.Screen options={{ title: 'Réglages du groupe' }} />
      <ErrorText error={error} />

      <View style={st.head}>
        <GroupTile group={{ ...look, photo_path: group.photo, system_key: system ? 'vip' : null }} size={64} />
        <View style={{ flex: 1, gap: 2 }}>
          <Title size={22}>{groupName({ name: group.name, system_key: system ? 'vip' : null })}</Title>
          <T muted size={14}>{[p.members.length === 1 ? '1 membre' : `${p.members.length} membres`, myRoleLine(mine.role)].filter(Boolean).join(' · ')}</T>
        </View>
      </View>

      {!system && mine.edit ? (
        <Section title="Modifier le groupe">
          <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
            <GroupTile group={{ ...look, photo_path: group.photo }} size={56} />
            <Input accessibilityLabel="Nom du groupe" value={look.name} maxLength={60} style={{ flex: 1 }}
              onChangeText={(name) => setDraft({ ...look, name })} />
          </View>
          <T size={14} weight="semibold" color={colors.textSoft}>Un emoji</T>
          <EmojiPicker value={look.emoji} onChange={(emoji) => setDraft({ ...look, emoji })} />
          <T size={14} weight="semibold" color={colors.textSoft}>Une couleur</T>
          <ColorPicker value={look.color} onChange={(c) => setDraft({ ...look, color: c as GroupColor })} colorsList={GROUP_COLOR_KEYS} />
          <Button label="Enregistrer" disabled={!changed || !look.name.trim()} loading={busy} onPress={() => void saveLook()} />
          <GroupPhotoField has={!!group.photo} disabled={busy} onPicked={(uri) => void changePhoto(uri)}
            onRemove={() => void changePhoto(null)} />
        </Section>
      ) : (
        <T muted size={13}>{system
          ? 'Tous les Membres VIP et au-dessus, tenu à jour tout seul : passer quelqu’un Membre VIP l’ajoute, le remettre Guest le retire (Administration → Membres).'
          : editLine}</T>
      )}

      {member ? (
        <Section title="Ma confidentialité">
          <ToggleRow label="Montrer mon numéro dans ce groupe" hint="Les membres de ce groupe le voient sur ta fiche profil. Caché par défaut."
            value={data.phoneGroups.has(group.id)} disabled={busy}
            onChange={(visible) => void run(supabase.rpc('set_group_phone_share', { grp: group.id, visible }))} />
        </Section>
      ) : null}

      {/* Vendredi Party : seule l'annonce des événements se règle (Co-admins et plus), jamais les rôles ni les droits.
          Base d'avant le 23.11 (legacy) : l'ancien écran des règles (« Tous les membres peuvent inviter », événements). */}
      {(system && rank >= roleRank('coadmin')) || (p.legacy && manage) ? (
        <Section title="Règles du groupe">
          {p.legacy && manage ? (
            <ToggleRow label="Tous les membres peuvent inviter"
              hint={p.rights.invite === 'members'
                ? 'Chaque membre peut ajouter quelqu’un et partager le lien du groupe.'
                : 'Seuls toi et ceux qui gèrent le groupe invitent et partagent le lien du groupe.'}
              value={p.rights.invite === 'members'} disabled={busy}
              onChange={(allowed) => void run(supabase.rpc('set_group_members_invite', { grp: group.id, allowed }),
                allowed ? 'Tous les membres peuvent inviter' : 'Seuls ceux qui gèrent le groupe invitent')} />
          ) : null}
          <GroupEventRules groupId={group.id} needApproval={!!p.events_need_approval} mode={p.announce_mode ?? 'request'} system={system}
            onSaved={() => void reload()} />
        </Section>
      ) : null}

      {manage && !p.legacy ? (
        <View style={{ gap: 10 }} testID="group-roles">
          <T style={st.kicker}>RÔLES DANS LE GROUPE</T>
          <View style={st.box}>
            {roleRows.map((r, i) => (
              <View key={r.key} style={[st.line, i ? st.lineTop : null]}>
                <View style={[st.badge, { backgroundColor: r.tint }]}><T size={13} weight="bold" color={colors.bg}>{r.short}</T></View>
                <View style={{ flex: 1, gap: 2 }}>
                  <T weight="semibold">{r.name}</T>
                  <T muted size={13}>{r.who}</T>
                </View>
              </View>
            ))}
          </View>
          <T muted size={13}>Touche un membre pour changer son rôle. Le créateur reste toujours admin du groupe.</T>
        </View>
      ) : null}

      {(manage || mine.remove) && !system ? (
        <Section title={`Membres · ${p.members.length}`}>
          {mine.invite ? <Button small variant="secondary" label="👋 Inviter des gens" onPress={() => router.push(`/group/${group.id}/invite`)} /> : null}
          {p.members.map((m) => (
            <Pressable key={m.id} accessibilityRole={touchable(m) ? 'button' : undefined} disabled={!touchable(m)}
              accessibilityLabel={touchable(m) ? `${personText(m.id, m.name)}, ${ROLE_TITLE[m.role]}` : undefined}
              onPress={() => setRoleOf(m)} style={({ pressed }) => [st.member, pressed && { opacity: 0.7 }]}>
              <Avatar id={m.id} name={m.name} photo={m.photo} size={34} profile={false} />
              <T style={{ flex: 1 }} numberOfLines={1}>{personText(m.id, m.name)}{m.id === me.id ? ' (toi)' : ''}</T>
              <T muted size={13}>{m.role === 'creator' ? 'Admin · créateur' : ROLE_TITLE[m.role]}</T>
              {touchable(m) ? <View style={st.chevron} /> : null}
            </Pressable>
          ))}
        </Section>
      ) : null}

      {mine.rules && !system && !p.legacy ? (
        <View style={{ gap: 10 }} testID="group-rights">
          <T style={st.kicker}>QUI PEUT…</T>
          <View style={st.box}>
            {RIGHT_KEYS.map((k, i) => {
              const who = whoText(k, p.rights[k], p.events_need_approval);
              return (
                <Pressable key={k} accessibilityRole="button" accessibilityLabel={`${RIGHTS[k].label} : ${who.text}`}
                  onPress={() => router.push({ pathname: '/group/[id]/right', params: { id: group.id, k } })}
                  style={({ pressed }) => [st.line, i ? st.lineTop : null, pressed && { backgroundColor: colors.fill }]}>
                  <View style={{ flex: 1, gap: 3 }}>
                    <T weight="semibold">{RIGHTS[k].label}</T>
                    <T size={13} weight="semibold" color={who.color}>{who.text}</T>
                  </View>
                  <View style={st.chevron} />
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}

      {manage && !p.legacy ? (
        <View style={{ gap: 10 }} testID="group-entry">
          <T style={st.kicker}>ENTRÉE DANS LE GROUPE</T>
          <View style={[st.box, { padding: 14, gap: 12 }]}>
            <ToggleRow label="Accepter chaque nouveau membre" value={p.join_approval} disabled={busy}
              hint="Qui ouvre le lien du groupe attend ton accord (ou celui d’un co-admin)."
              onChange={(approval) => void run(supabase.rpc('set_group_join_approval', { grp: group.id, approval }),
                approval ? 'Chaque nouveau membre attend ton accord' : 'Le lien fait entrer directement')} />
            {p.requests.map((r) => (
              <View key={r.id} style={st.member}>
                <Avatar id={r.id} name={r.name} photo={r.photo} size={34} />
                <T style={{ flex: 1 }} numberOfLines={1}>{personText(r.id, r.name)} demande à entrer</T>
                <Button small variant="secondary" label="Refuser" disabled={busy}
                  onPress={() => void run(supabase.rpc('decide_group_join', { grp: group.id, member: r.id, accept: false }), 'Demande refusée')} />
                <Button small label="Accepter" disabled={busy}
                  onPress={() => void run(supabase.rpc('decide_group_join', { grp: group.id, member: r.id, accept: true }), `${r.name} est dans le groupe`)} />
              </View>
            ))}
            <View style={st.rule} />
            <View style={st.member}>
              <View style={{ flex: 1, gap: 3 }}>
                <T weight="semibold">Lien d’invitation</T>
                <T muted size={13}>{p.link_active ? 'Actif · renouvelé, l’ancien lien ne marche plus' : 'Pas encore créé'}</T>
              </View>
              <ConfirmButton small label="Renouveler" confirmLabel="Nouveau lien"
                onConfirm={() => run(supabase.rpc('group_invite_link', { grp: group.id, renew: true }), 'Nouveau lien créé : l’ancien ne marche plus')} />
            </View>
          </View>
        </View>
      ) : null}

      {manage ? <InviteLinkCard kind="group" id={group.id} /> : null}

      {member && !system && mine.role !== 'creator' ? (
        // Quitter soi-même (recette du 10.11) : la base le permet (politique « quitter le groupe »), jamais Vendredi Party.
        <ConfirmButton label="Quitter le groupe" confirmLabel="Confirmer : quitter le groupe"
          onConfirm={async () => {
            if (await run(supabase.from('member_group_members').delete().eq('group_id', group.id).eq('user_id', me.id).select('user_id').single())) {
              router.replace('/groups');
            }
          }} />
      ) : null}
      {mine.owner && !system ? (
        <View style={{ gap: 10 }}>
          {!p.legacy ? (
            <Pressable accessibilityRole="button" onPress={() => setHanding(true)} style={({ pressed }) => [st.handOver, pressed && { opacity: 0.8 }]}>
              <T weight="bold" color="#FF8FB8" style={{ textAlign: 'center' }}>Transmettre le groupe à un autre admin</T>
            </Pressable>
          ) : null}
          <ConfirmButton label="Supprimer le groupe" confirmLabel="Confirmer la suppression"
            onConfirm={async () => {
              const photo = group.photo;
              if (await run(supabase.from('member_groups').delete().eq('id', group.id))) {
                if (photo) void supabase.storage.from(GROUP_PHOTOS).remove([photo]);  // la photo part avec le groupe
                router.replace('/groups');
              }
            }} />
          <T muted size={13}>Les invités qui ont déjà répondu gardent l’accès à leurs événements.</T>
        </View>
      ) : null}

      <RoleSheet member={roleOf} manage={manage && !p.legacy} busy={busy} onClose={() => setRoleOf(null)}
        onRole={(m, role) => { setRoleOf(null); void run(supabase.rpc('set_group_role', { grp: group.id, member: m.id, role }), `${m.name} : ${ROLE_TITLE[role]}`); }}
        onRemove={(m) => { setRoleOf(null); void run(supabase.from('member_group_members').delete().eq('group_id', group.id).eq('user_id', m.id).select('user_id'), `${m.name} a quitté le groupe`); }} />
      <HandOverSheet visible={handing} members={p.members.filter((m) => m.role !== 'creator')} busy={busy} onClose={() => setHanding(false)}
        onPick={(m) => { setHanding(false); void run(supabase.rpc('transfer_group', { grp: group.id, member: m.id }), `${m.name} est maintenant l’admin du groupe`); }} />
      {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
    </Screen>
  );
}

/** Rôle d'un membre (maquette « Rôle de … dans le groupe ») : Membre / Organisateur / Co-admin, sa fiche, le retirer. */
function RoleSheet({ member, manage, busy, onClose, onRole, onRemove }: {
  member: PanelMember | null; manage: boolean; busy: boolean; onClose: () => void;
  onRole: (m: PanelMember, role: Exclude<GroupRole, 'creator'>) => void; onRemove: (m: PanelMember) => void;
}) {
  const top = useSheetTop();
  const personText = usePersonText();
  useSheetSignal(!!member);
  if (!member) return null;
  const since = member.since ? new Date(member.since).toLocaleDateString('fr-CH', { day: 'numeric', month: 'long', timeZone: 'Europe/Zurich' }) : null;
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={[st.overlay, { paddingTop: top }]}>
        <SheetBackdrop onPress={onClose} />
        <View style={st.sheet} accessibilityViewIsModal accessibilityLabel={`Rôle de ${member.name} dans le groupe`}>
          <SheetTop onClose={onClose} />
          <View style={st.member}>
            <Avatar id={member.id} name={member.name} photo={member.photo} size={56} profile={false} />
            <View style={{ flex: 1, gap: 2 }}>
              <Title size={20}>{personText(member.id, member.name)}</Title>
              {since ? <T muted size={13}>Dans le groupe depuis le {since}</T> : null}
            </View>
          </View>
          {manage ? (
            <>
              <T style={st.kicker}>RÔLE DANS LE GROUPE</T>
              {(['member', 'organizer', 'coadmin'] as const).map((r) => {
                const on = member.role === r;
                return (
                  <Pressable key={r} accessibilityRole="radio" accessibilityState={{ checked: on, disabled: busy }} aria-checked={on} disabled={busy}
                    accessibilityLabel={ROLE_TITLE[r]} onPress={() => (on ? onClose() : onRole(member, r))}
                    style={[st.choice, on && st.choiceOn]}>
                    <View style={[st.ring, on && { borderColor: colors.accentSoft }]}>{on ? <View style={st.dot} /> : null}</View>
                    <View style={{ flex: 1, gap: 3 }}>
                      <T weight="bold">{ROLE_TITLE[r]}</T>
                      <T muted size={13}>{ROLE_DETAIL[r]}</T>
                    </View>
                  </Pressable>
                );
              })}
            </>
          ) : null}
          <Button variant="secondary" label="Voir sa fiche" onPress={() => { onClose(); openProfile(member.id); }} />
          <ConfirmButton label="Retirer du groupe" confirmLabel="Confirmer : retirer" onConfirm={() => onRemove(member)} />
        </View>
      </View>
    </Modal>
  );
}

/** « Transmettre le groupe à un autre admin » : un membre devient l'admin ; l'ancien admin reste co-admin. */
function HandOverSheet({ visible, members, busy, onClose, onPick }: {
  visible: boolean; members: PanelMember[]; busy: boolean; onClose: () => void; onPick: (m: PanelMember) => void;
}) {
  const top = useSheetTop();
  const personText = usePersonText();
  const [picked, setPicked] = useState<PanelMember | null>(null);
  useSheetSignal(visible);
  if (!visible) return null;
  const close = () => { setPicked(null); onClose(); };
  return (
    <Modal visible transparent animationType="fade" onRequestClose={close}>
      <View style={[st.overlay, { paddingTop: top }]}>
        <SheetBackdrop onPress={close} />
        <View style={st.sheet} accessibilityViewIsModal accessibilityLabel="Transmettre le groupe">
          <SheetTop onClose={close} />
          <Title size={20}>Transmettre le groupe</Title>
          <T muted size={14}>La personne choisie devient l’admin du groupe : elle seule pourra le supprimer ou le transmettre. Tu restes co-admin.</T>
          {members.length ? members.map((m) => (
            <Pressable key={m.id} accessibilityRole="radio" accessibilityState={{ checked: picked?.id === m.id }} aria-checked={picked?.id === m.id} accessibilityLabel={personText(m.id, m.name)}
              onPress={() => setPicked(m)} style={[st.choice, picked?.id === m.id && st.choiceOn]}>
              <Avatar id={m.id} name={m.name} photo={m.photo} size={34} profile={false} />
              <T style={{ flex: 1 }} weight="semibold">{personText(m.id, m.name)}</T>
              <T muted size={13}>{ROLE_TITLE[m.role]}</T>
            </Pressable>
          )) : <T muted>Personne d’autre dans le groupe pour l’instant.</T>}
          <Button label={picked ? `Transmettre à ${personText(picked.id, picked.name)}` : 'Choisis un membre'} disabled={!picked || busy}
            onPress={() => { if (picked) { onPick(picked); setPicked(null); } }} />
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  kicker: { fontSize: 13, fontWeight: '700', letterSpacing: 1.4, color: colors.muted },
  box: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, overflow: 'hidden' },
  line: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 12, minHeight: 62 },
  lineTop: { borderTopWidth: 1, borderTopColor: colors.line },
  badge: { width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  chevron: { width: 9, height: 9, borderTopWidth: 2, borderRightWidth: 2, borderColor: '#7E74A6', transform: [{ rotate: '45deg' }], marginRight: 4 },
  member: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  rule: { height: 1, backgroundColor: colors.line },
  handOver: { minHeight: 52, borderRadius: 16, borderWidth: 1, borderColor: '#5A2340', backgroundColor: '#2A1426', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: '#1C1535', borderWidth: 1, borderColor: colors.lineStrong },
  choice: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, minHeight: 64, borderRadius: 18, borderWidth: 2, borderColor: colors.line, backgroundColor: colors.surface },
  choiceOn: { borderColor: colors.accentSoft, backgroundColor: '#2A1A3D' },
  ring: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: '#7E74A6', alignItems: 'center', justifyContent: 'center' },
  dot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.accentSoft },
});
