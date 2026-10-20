import { Redirect } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Chip, ErrorText, Screen, s, Section, T, ToggleRow } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { ROLE_ORDER, roleLabel, roleRank, type MemberRole, type Permission } from '@/lib/types';

/** Rôles et droits : on choisit un rôle (en dessous du sien), puis on coche ce qu'il peut faire. */
export default function Roles() {
  const { can, rank, perms: mine } = useAuth();
  const editable = [...ROLE_ORDER].reverse().filter((r) => roleRank(r) < rank);
  const [role, setRole] = useState<MemberRole>(editable.includes('member') ? 'member' : editable[0] ?? 'guest');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const { data, reload } = useQuery(async () => {
    const [catalog, grants] = await Promise.all([
      supabase.from('permissions').select('*').order('sort'),
      supabase.from('role_permissions').select('role, perm'),
    ]);
    return { catalog: must(catalog) as Permission[], grants: must(grants) as { role: MemberRole; perm: string }[] };
  }, []);

  if (!(can('roles.manage') || rank >= 99)) return <Redirect href="/" />;

  const granted = (perm: string) => !!data?.grants.some((g) => g.role === role && g.perm === perm);
  async function toggle(perm: string, on: boolean) {
    setSaving(perm);
    setError(null);
    const { error } = await supabase.rpc('set_role_permission', { target: role, perm, granted: on });
    if (error) setError(error.message.replace(/^forbidden: /, ''));
    await reload();
    setSaving(null);
  }

  const groups = [...new Set((data?.catalog ?? []).map((p) => p.grp))];
  return (
    <Screen edges={[]}>
      <T muted size={14}>Choisis un rôle, puis coche ce qu’il peut faire. Les changements s’appliquent tout de suite, à tous les comptes de ce rôle.{rank >= 99 ? ' En tant que root, tu as toujours tous les droits.' : ' Tu ne peux donner que les droits que tu as toi-même.'}</T>
      <View style={s.wrap}>
        {editable.map((r) => <Chip key={r} label={roleLabel[r]} selected={role === r} onPress={() => setRole(r)} />)}
      </View>
      <ErrorText error={error} />
      {groups.map((grp) => (
        <Section key={grp} title={grp}>
          {data!.catalog.filter((p) => p.grp === grp).map((p) => {
            const on = granted(p.key);
            return (
              <ToggleRow
                key={p.key}
                label={p.label}
                hint={p.hint ?? undefined}
                value={on}
                disabled={saving !== null || (!on && rank < 99 && !mine.includes(p.key))}
                onChange={(v) => { void toggle(p.key, v); }}
              />
            );
          })}
        </Section>
      ))}
    </Screen>
  );
}
