import { useState } from 'react';
import { View } from 'react-native';

import { InviteLinkCard } from '@/components/InviteLinkCard';
import { Avatar, Button, Card, Chip, ConfirmButton, ErrorText, Input, Screen, s, Section, T, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { roleLabel, VIP_GROUP_KEY, type MemberGroup, type Profile } from '@/lib/types';

type Invitation = { id: string; group_id: string; group: string; invited_by: string | null; at: string };

/** Groupes de membres pour inviter à un événement privé : partagés entre créateurs, modifiables par leur auteur et les admins. */
export default function GroupsScreen() {
  const me = useMe();
  const { can } = useAuth();
  const [name, setName] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guest, setGuest] = useState('');
  const [invited, setInvited] = useState<string | null>(null);

  const { data, reload, error: loadError } = useQuery(async () => {
    const [groups, members, privacy, invitations] = await Promise.all([
      supabase.from('member_groups').select('id, name, created_by, system_key, member_group_members(user_id)').order('name'),
      supabase.from('profiles').select('id, display_name, role, avatar_url').eq('status', 'active').order('display_name'),
      supabase.rpc('my_privacy'),
      supabase.rpc('my_group_invitations'),
    ]);
    // Vendredi Party en premier : c'est le groupe de tout le monde (VIP et au-dessus).
    const list = (must(groups) as MemberGroup[]).sort((a, b) => Number(b.system_key === VIP_GROUP_KEY) - Number(a.system_key === VIP_GROUP_KEY));
    return { groups: list, members: must(members) as Pick<Profile, 'id' | 'display_name' | 'role' | 'avatar_url'>[],
      phoneGroups: new Set(((privacy.data as { phone_groups?: string[] } | null)?.phone_groups) ?? []),
      invitations: (invitations.data ?? []) as Invitation[] };
  }, []);

  async function run(p: PromiseLike<{ error: { message: string } | null }>) {
    setBusy(true);
    const { error } = await p;
    setError(error ? (error.message.includes('duplicate') ? 'Déjà dans le groupe.' : 'La modification n’a pas été enregistrée. Réessaie.') : null);
    await reload();
    setBusy(false);
    return !error;
  }

  async function create() {
    const clean = name.trim();
    if (!clean) return;
    setBusy(true);
    const { data: created, error } = await supabase.from('member_groups').insert({ name: clean, created_by: me.id }).select('id').single();
    setBusy(false);
    if (error) return setError('Le groupe n’a pas été créé. Réessaie.');
    setName('');
    setOpen(created.id as string);
    await reload();
  }

  const people = new Map((data?.members ?? []).map((m) => [m.id, m]));

  async function sharePhone(group: string, visible: boolean) {
    await run(supabase.rpc('set_group_phone_share', { grp: group, visible }));
  }

  async function answer(inv: string, accept: boolean) {
    await run(supabase.rpc('answer_group_invitation', { inv, accept }));
  }

  /** Inviter par surnom (compte existant) ou par numéro (inscrit ou pas : l'invitation l'attend). */
  async function invite(group: string) {
    const typed = guest.trim();
    if (!typed) return;
    const digits = typed.replace(/\D/g, '');
    const byPhone = /^[+0-9][0-9 .()-]{6,}$/.test(typed) && digits.length >= 8;
    const member = byPhone ? null : data?.members.find((m) => m.display_name.toLowerCase() === typed.toLowerCase().replace(/^@/, ''));
    if (!byPhone && !member) return setError('Personne avec ce surnom. Essaie son numéro de téléphone.');
    const phone = byPhone ? (digits.startsWith('0') && digits.length === 10 ? `41${digits.slice(1)}` : digits) : null;
    setBusy(true);
    const { data: res, error } = await supabase.rpc('invite_to_group', { grp: group, member: member?.id ?? null, phone });
    setBusy(false);
    if (error) return setError(error.message.replace(/^\w+: /, ''));
    setError(null);
    setGuest('');
    setInvited((res as { invited: string }).invited === 'member'
      ? `${member?.display_name ?? 'La personne'} a reçu ton invitation (Réglages → Groupes).`
      : 'Invitation gardée pour ce numéro : elle l’attendra dès son inscription.');
  }

  return (
    <Screen edges={[]}>
      <T muted>Un groupe sert à inviter plusieurs personnes d’un coup à un événement (Guests compris). Quelqu’un qui rejoint le groupe plus tard est aussi invité aux événements à venir.</T>
      <ErrorText error={error ?? loadError} />

      {data?.invitations.length ? (
        <Section title="Invitations reçues">
          {data.invitations.map((i) => (
            <Card key={i.id}>
              <T weight="bold">{i.group}</T>
              <T muted size={13}>{i.invited_by ?? 'Quelqu’un'} t’invite dans ce groupe</T>
              <View style={s.row}>
                <Button small label="Accepter" style={{ flex: 1 }} disabled={busy} onPress={() => void answer(i.id, true)} />
                <Button small variant="secondary" label="Refuser" style={{ flex: 1 }} disabled={busy} onPress={() => void answer(i.id, false)} />
              </View>
            </Card>
          ))}
        </Section>
      ) : null}

      <Section title="Nouveau groupe">
        <View style={s.row}>
          <Input accessibilityLabel="Nom du groupe" placeholder="Ex. Les footeux" value={name} onChangeText={setName} maxLength={60} style={{ flex: 1 }} onSubmitEditing={create} />
          <Button small label="Créer" disabled={!name.trim()} loading={busy && !!name.trim()} onPress={create} />
        </View>
      </Section>

      <Section title="Groupes">
        {data && !data.groups.length ? <T muted>Aucun groupe pour l’instant.</T> : null}
        {data?.groups.map((g) => {
          const system = g.system_key === VIP_GROUP_KEY;
          const mine = !system && (g.created_by === me.id || can('events.manage_all'));
          const inside = new Set(g.member_group_members.map((m) => m.user_id));
          const expanded = open === g.id;
          return (
            <Card key={g.id}>
              <View style={[s.row, { justifyContent: 'space-between' }]}>
                <View style={{ flex: 1 }}>
                  <T weight="bold">{g.name}</T>
                  <T muted size={13} numberOfLines={expanded ? undefined : 1}>
                    {inside.size ? [...inside].map((id) => people.get(id)?.display_name ?? '?').join(', ') : 'Personne pour l’instant'}
                  </T>
                </View>
                {mine ? <Button small variant="secondary" label={expanded ? 'Fermer' : 'Modifier'} onPress={() => setOpen(expanded ? null : g.id)} /> : null}
              </View>
              {inside.size ? (
                <View style={s.wrap} accessibilityLabel="Membres du groupe : touche une photo pour voir le profil">
                  {[...inside].map((id) => {
                    const m = people.get(id);
                    return m ? <Avatar key={id} id={id} name={m.display_name} photo={m.avatar_url} size={34} /> : null;
                  })}
                </View>
              ) : null}
              {inside.has(me.id) ? (
                <ToggleRow
                  label="Montrer mon numéro dans ce groupe"
                  hint="Les membres de ce groupe le voient sur ta fiche profil. Caché par défaut."
                  value={!!data?.phoneGroups.has(g.id)}
                  disabled={busy}
                  onChange={(v) => void sharePhone(g.id, v)}
                />
              ) : null}
              {system ? <T muted size={13}>Tous les Membres VIP et au-dessus, tenu à jour tout seul : passer quelqu’un Membre VIP l’ajoute, le remettre Guest le retire (Administration → Membres).</T> : null}
              {expanded && mine ? (
                <>
                  <View style={s.wrap}>
                    {data.members.map((m) => (
                      <Chip
                        key={m.id}
                        label={m.role === 'guest' || m.role === 'guestplus' ? `${m.display_name} · ${roleLabel[m.role]}` : m.display_name}
                        selected={inside.has(m.id)}
                        disabled={busy}
                        onPress={() => run(inside.has(m.id)
                          ? supabase.from('member_group_members').delete().eq('group_id', g.id).eq('user_id', m.id)
                          : supabase.from('member_group_members').insert({ group_id: g.id, user_id: m.id }))}
                      />
                    ))}
                  </View>
                  <View style={s.row}>
                    <Input accessibilityLabel="Inviter par surnom ou numéro" placeholder="Inviter : surnom ou numéro" value={guest}
                      onChangeText={(v) => { setGuest(v); setInvited(null); }} style={{ flex: 1 }} onSubmitEditing={() => void invite(g.id)} />
                    <Button small label="Inviter" disabled={!guest.trim() || busy} onPress={() => void invite(g.id)} />
                  </View>
                  {invited ? <T muted size={13}>{invited}</T> : null}
                  <InviteLinkCard kind="group" id={g.id} />
                  <ConfirmButton small label="Supprimer le groupe" confirmLabel="Confirmer la suppression" onConfirm={() => run(supabase.from('member_groups').delete().eq('id', g.id))} />
                  <T muted size={13}>Les invités qui ont déjà répondu gardent l’accès à leurs événements.</T>
                </>
              ) : null}
            </Card>
          );
        })}
      </Section>
    </Screen>
  );
}
