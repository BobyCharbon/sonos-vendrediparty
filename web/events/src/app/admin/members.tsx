import { Redirect } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Chip, ErrorText, Input, Screen, s, Section, T } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { check, must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import type { MemberRole, Profile } from '@/lib/types';

const roleLabel: Record<MemberRole, string> = { admin: 'Admin', coadmin: 'Co-admin', member: 'Membre' };

export default function Members() {
  const me = useMe();
  const { isAdmin } = useAuth();
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const updating = useRef(false);
  const { data, error: loadError, loading, reload } = useQuery(
    async () => must(await supabase.rpc('get_member_directory').order('display_name')) as Profile[],
    [],
  );

  if (!isAdmin) return <Redirect href="/" />;

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
      setError(message.includes('last_admin') ? 'Désigne d’abord un autre administrateur actif.' : message);
    } finally {
      updating.current = false;
      setBusy(false);
    }
  }

  const q = search.trim().toLowerCase();
  const rows = (data ?? []).filter((p) => !q || p.display_name.toLowerCase().includes(q) || p.phone?.includes(q));
  const active = rows.filter((p) => p.status === 'active');
  const others = rows.filter((p) => p.status !== 'active');

  return (
    <Screen edges={[]}>
      <Input placeholder="Rechercher un membre" value={search} onChangeText={setSearch} />
      <ErrorText error={error ?? loadError} />
      {loadError ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
      {loading ? <T muted>Chargement des membres…</T> : null}
      <Section title={`Membres (${active.length})`}>{active.map((person) => <MemberRow key={person.id} person={person} me={me} busy={busy} onUpdate={update} />)}</Section>
      {others.length ? <Section title="En attente ou retirés">{others.map((person) => <MemberRow key={person.id} person={person} me={me} busy={busy} onUpdate={update} />)}</Section> : null}
    </Screen>
  );
}

function MemberRow({ person: p, me, busy, onUpdate }: {
  person: Profile; me: Profile; busy: boolean; onUpdate: (id: string, patch: Partial<Profile>) => Promise<void>;
}) {
  return (
    <View key={p.id} style={{ gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.line }}>
      <View style={s.row}>
        <Avatar id={p.id} name={p.display_name || '?'} />
        <View style={{ flex: 1 }}>
          <T weight="semibold">{p.display_name || 'Sans prénom'}{p.id === me.id ? ' (toi)' : ''}</T>
          <T muted size={12}>{roleLabel[p.role]} · {p.phone}</T>
        </View>
      </View>
      {p.id !== me.id ? (
        <View style={s.wrap}>
          {p.status === 'active' ? (
            <>
              {me.role === 'admin'
                ? (['member', 'coadmin', 'admin'] as MemberRole[]).map((r) => (
                    <Chip key={r} label={roleLabel[r]} selected={p.role === r} disabled={busy} onPress={() => onUpdate(p.id, { role: r })} />
                  ))
                : null}
              <Chip label="Retirer l’accès" color={colors.coral} disabled={busy} onPress={() => onUpdate(p.id, { status: 'banned' })} />
            </>
          ) : (
            <Chip label={p.status === 'pending' ? 'Accepter' : 'Réintégrer'} disabled={busy} onPress={() => onUpdate(p.id, { status: 'active' })} />
          )}
        </View>
      ) : null}
    </View>
  );
}
