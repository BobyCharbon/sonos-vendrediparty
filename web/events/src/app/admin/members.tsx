import { Redirect } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Chip, ErrorText, Input, Screen, s, Section, T } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { hasCompleteIdentity } from '@/lib/profile';
import { check, must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { ROLE_ORDER, roleLabel, roleRank, type MemberRole, type Profile } from '@/lib/types';

const ROOT_ID = '298ff6e0-07b2-4127-bb69-d254dd63a3d5';

/** Membres : rôles et accès. On ne touche qu'aux comptes d'un rôle inférieur au sien, et on ne donne qu'un rôle inférieur au sien. */
export default function Members() {
  const me = useMe();
  const { can, rank } = useAuth();
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const updating = useRef(false);
  const { data, error: loadError, loading, reload } = useQuery(
    async () => must(await supabase.rpc('get_member_directory').order('display_name')) as Profile[],
    [],
  );

  if (!(can('members.roles') || can('members.ban') || can('members.view_identity'))) return <Redirect href="/" />;

  async function update(id: string, patch: Partial<Profile>) {
    if (updating.current) return;
    updating.current = true;
    setBusy(true);
    setError(null);
    try {
      check(await supabase.from('profiles').update(patch).eq('id', id));
      await reload();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message.includes('last_admin') ? 'Désigne d’abord un autre administrateur actif.'
        : message.includes('profile_incomplete') ? 'Ce compte doit d’abord renseigner son nom, son prénom, son surnom et sa photo.'
        : message.replace(/^forbidden: /, ''));
    } finally {
      updating.current = false;
      setBusy(false);
    }
  }

  const q = search.trim().toLowerCase();
  const rows = (data ?? []).filter((p) => !q || [p.display_name, p.first_name, p.last_name, p.phone].some((value) => value?.toLowerCase().includes(q)));
  const byRole = (r: MemberRole) => rows.filter((p) => p.status === 'active' && p.role === r);
  const banned = rows.filter((p) => p.status === 'banned');
  const row = (person: Profile) => <MemberRow key={person.id} person={person} me={me} myRank={rank} canRoles={can('members.roles')} canBan={can('members.ban')} busy={busy} onUpdate={update} />;

  return (
    <Screen edges={[]}>
      <Input placeholder="Rechercher (surnom, prénom, nom, numéro)" value={search} onChangeText={setSearch} />
      <ErrorText error={error ?? loadError} />
      {loadError ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
      {loading ? <T muted>Chargement des membres…</T> : null}
      {[...ROLE_ORDER].reverse().map((r) => {
        const list = byRole(r);
        return list.length ? <Section key={r} title={`${roleLabel[r]} (${list.length})`}>{list.map(row)}</Section> : null;
      })}
      {banned.length ? <Section title={`Accès retiré (${banned.length})`}>{banned.map(row)}</Section> : null}
    </Screen>
  );
}

function MemberRow({ person: p, me, myRank, canRoles, canBan, busy, onUpdate }: {
  person: Profile; me: Profile; myRank: number; canRoles: boolean; canBan: boolean; busy: boolean;
  onUpdate: (id: string, patch: Partial<Profile>) => Promise<void>;
}) {
  const root = p.id === ROOT_ID;
  const below = !root && p.id !== me.id && roleRank(p.role) < myRank;
  const roles = ROLE_ORDER.filter((r) => roleRank(r) < myRank);
  return (
    <View style={{ gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.line }}>
      <View style={s.row}>
        <Avatar id={p.id} name={p.display_name || '?'} photo={p.avatar_url} />
        <View style={{ flex: 1 }}>
          <T weight="semibold">{p.display_name || 'Profil à compléter'}{p.id === me.id ? ' (toi)' : ''}</T>
          {p.first_name || p.last_name ? <T muted>{[p.first_name, p.last_name].filter(Boolean).join(' ')}</T> : null}
          <T muted size={12}>{root ? '👑 Root' : roleLabel[p.role]}{p.phone ? ` · +${p.phone.replace(/^\+/, '')}` : ''}</T>
        </View>
      </View>
      {below && (canRoles || canBan) ? (
        <View style={s.wrap}>
          {p.status === 'active' && canRoles
            ? roles.map((r) => (
                <Chip key={r} label={roleLabel[r]} selected={p.role === r} disabled={busy || (roleRank(r) > 0 && !hasCompleteIdentity(p))} onPress={() => onUpdate(p.id, { role: r })} />
              ))
            : null}
          {canBan ? (
            p.status === 'active'
              ? <Chip label="Retirer l’accès" color={colors.coral} disabled={busy} onPress={() => onUpdate(p.id, { status: 'banned' })} />
              : <Chip label="Réintégrer" disabled={busy} onPress={() => onUpdate(p.id, { status: 'active' })} />
          ) : null}
          {p.status === 'active' && canRoles && !hasCompleteIdentity(p) ? <T muted size={13}>Profil incomplet : il reste invité tant qu’il manque nom, prénom, surnom ou photo.</T> : null}
        </View>
      ) : null}
    </View>
  );
}
