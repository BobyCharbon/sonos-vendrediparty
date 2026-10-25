import { useState } from 'react';
import { View } from 'react-native';

import { parseLoginPhone } from '@/lib/phone';
import { roleLabel, VIP_GROUP_KEY, type MemberGroup, type MemberRole } from '@/lib/types';
import { Button, Chip, ErrorText, Input, s, T } from './ui';

/** Qui voit la sortie (base : can_see_event, migration 20261025160000) :
 * - « public » : tous les comptes (Guests compris) et le lien public → visibility 'all' + public_link ;
 * - « invite » : groupe Vendredi Party (vip) et/ou groupes choisis, plus des personnes ajoutées une à une
 *   (compte ou numéro de téléphone) → visibility 'all' si Vendredi Party est coché, sinon 'invited'. */
export type Audience = 'public' | 'invite';
export type AudienceValue = { audience: Audience; vip: boolean; group_ids: string[]; invitees: string[]; phones: string[] };
export type Person = { id: string; display_name: string; role: MemberRole };

export const DEFAULT_AUDIENCE: AudienceValue = { audience: 'invite', vip: true, group_ids: [], invitees: [], phones: [] };

export function audienceFromEvent(e: {
  visibility: 'all' | 'invited'; public_link: boolean; event_groups: { group_id: string }[];
  event_invites: { user_id: string; via_group: boolean }[]; event_phone_invites?: { phone: string }[];
}): AudienceValue {
  return {
    audience: e.visibility === 'all' && e.public_link ? 'public' : 'invite',
    vip: e.visibility === 'all' && !e.public_link,
    group_ids: e.event_groups.map((g) => g.group_id),
    invitees: e.event_invites.filter((i) => !i.via_group).map((i) => i.user_id),
    phones: (e.event_phone_invites ?? []).map((p) => p.phone),
  };
}

export function audienceToEvent(v: AudienceValue): { visibility: 'all' | 'invited'; public_link: boolean } {
  if (v.audience === 'public') return { visibility: 'all', public_link: true };
  return { visibility: v.vip ? 'all' : 'invited', public_link: false };
}

/** Ce qui est réellement enregistré (une sortie publique n'a ni groupes ni invités un à un). */
export function audienceChildren(v: AudienceValue) {
  const invite = v.audience === 'invite';
  return { group_ids: invite ? v.group_ids : [], invitees: invite ? v.invitees : [], phones: invite ? v.phones : [] };
}

export function audienceError(v: AudienceValue): string | null {
  if (v.audience === 'invite' && !v.vip && !v.group_ids.length && !v.invitees.length && !v.phones.length) {
    return 'Choisis qui inviter : le groupe Vendredi Party, un groupe ou des personnes';
  }
  return null;
}

/** Numéro saisi (076…, +33…, 0041…) → format d'Auth : indicatif + numéro, sans « + ». */
export function phoneForInvite(raw: string): { phone: string; formatted: string } | null {
  const parsed = parseLoginPhone(raw, 'CH');
  return parsed ? { phone: parsed.number.replace(/^\+/, ''), formatted: parsed.formatted } : null;
}

const PEOPLE_SHOWN = 24;

export function AudiencePicker({ value, onChange, groups, people, meId, allGroups }: {
  value: AudienceValue;
  onChange: (v: AudienceValue) => void;
  groups: MemberGroup[];
  people: Person[];
  meId: string;
  allGroups: boolean;  // admins : tous les groupes ; sinon ceux qu'on a créés ou dont on fait partie
}) {
  const [search, setSearch] = useState('');
  const [phone, setPhone] = useState('');
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const set = (patch: Partial<AudienceValue>) => onChange({ ...value, ...patch });
  const toggle = (key: 'group_ids' | 'invitees', id: string) =>
    set({ [key]: value[key].includes(id) ? value[key].filter((x) => x !== id) : [...value[key], id] });

  const vipGroup = groups.find((g) => g.system_key === VIP_GROUP_KEY);
  const choosable = groups.filter((g) => g.system_key !== VIP_GROUP_KEY
    && (allGroups || g.created_by === meId || g.member_group_members.some((m) => m.user_id === meId)));
  const q = search.trim().toLowerCase();
  const others = people.filter((p) => p.id !== meId);
  const picked = others.filter((p) => value.invitees.includes(p.id));
  const found = q ? others.filter((p) => !value.invitees.includes(p.id) && p.display_name.toLowerCase().includes(q)).slice(0, PEOPLE_SHOWN) : [];
  const label = (p: Person) => (p.role === 'guest' ? `${p.display_name} · ${roleLabel.guest}` : p.display_name);

  function addPhone() {
    const parsed = phoneForInvite(phone);
    if (!parsed) return setPhoneError('Numéro invalide. Ex. 079 123 45 67 ou +33 6 12 34 56 78');
    setPhoneError(null);
    setPhone('');
    if (!value.phones.includes(parsed.phone)) set({ phones: [...value.phones, parsed.phone] });
  }

  return (
    <View style={{ gap: 10 }}>
      <T muted size={13}>Qui est invité ?</T>
      <View style={s.wrap} accessibilityRole="radiogroup" accessibilityLabel="Qui est invité">
        <Chip label="Sur invitation" selected={value.audience === 'invite'} onPress={() => set({ audience: 'invite' })} />
        <Chip label="Publique + lien" selected={value.audience === 'public'} onPress={() => set({ audience: 'public' })} />
      </View>
      {value.audience === 'public' ? (
        <T muted size={13}>Tous les comptes Party la voient, Guests compris, et toute personne qui a le lien : elle voit l’essentiel et peut répondre après connexion par SMS.</T>
      ) : (
        <>
          <Chip
            label={`👥 Vendredi Party${vipGroup ? ` · ${vipGroup.member_group_members.length}` : ''}`}
            selected={value.vip}
            onPress={() => set({ vip: !value.vip })}
          />
          <T muted size={13}>Tous les Membres VIP et au-dessus. Ajoute d’autres groupes ou des personnes en plus si tu veux.</T>
          {choosable.length ? (
            <View style={s.wrap}>
              {choosable.map((g) => (
                <Chip key={g.id} label={`${g.name} · ${g.member_group_members.length}`} selected={value.group_ids.includes(g.id)} onPress={() => toggle('group_ids', g.id)} />
              ))}
            </View>
          ) : null}
          <T muted size={13}>Ajouter des personnes</T>
          {picked.length ? (
            <View style={s.wrap}>{picked.map((p) => <Chip key={p.id} label={`✕ ${label(p)}`} selected onPress={() => toggle('invitees', p.id)} />)}</View>
          ) : null}
          <Input accessibilityLabel="Chercher une personne à inviter" placeholder="Chercher par surnom" value={search} onChangeText={setSearch} />
          {found.length ? <View style={s.wrap}>{found.map((p) => <Chip key={p.id} label={`+ ${label(p)}`} onPress={() => toggle('invitees', p.id)} />)}</View> : null}
          {q && !found.length ? <T muted size={13}>Personne avec ce surnom : invite par numéro ci-dessous.</T> : null}
          <View style={s.row}>
            <Input accessibilityLabel="Inviter par numéro de téléphone" placeholder="Numéro : 079 123 45 67" keyboardType="phone-pad" value={phone}
              onChangeText={setPhone} onSubmitEditing={addPhone} style={{ flex: 1 }} />
            <Button small label="Inviter" disabled={!phone.trim()} onPress={addPhone} />
          </View>
          <ErrorText error={phoneError} />
          {value.phones.length ? (
            <View style={s.wrap}>{value.phones.map((p) => <Chip key={p} label={`✕ +${p}`} selected onPress={() => set({ phones: value.phones.filter((x) => x !== p) })} />)}</View>
          ) : null}
          <T muted size={13}>Un numéro sans compte voit l’événement dès qu’il se connecte à Party avec ce numéro. Les invités reçoivent une invitation privée.</T>
        </>
      )}
    </View>
  );
}
