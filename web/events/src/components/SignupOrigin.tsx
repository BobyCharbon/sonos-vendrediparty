import { View } from 'react-native';

import { Card, Section, T } from './ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

/** Droit « Voir l'origine des inscriptions » (avis 01da90202166, 22.11) ; Root l'a toujours. */
export const SIGNUP_PERM = 'members.signup_source';

type Count = { label: string; last30: number; total: number };
type Stats = { sources: Count[]; platforms: Count[] };

/** Fiche d'un membre › « Inscrit via … » (phrase écrite par la base). Rien sans le droit. */
export function SignupOriginLine({ id }: { id: string }) {
  const { can } = useAuth();
  const allowed = can(SIGNUP_PERM);
  const { data } = useQuery(async () => {
    if (!allowed) return null;
    const { data, error } = await supabase.rpc('admin_signup_sources', { target: id });
    if (error) return null;
    return ((data as { line: string }[] | null) ?? [])[0]?.line ?? null;
  }, [id, allowed]);
  if (!data) return null;
  return (
    <Section title="Inscription">
      <T>{data}</T>
      <T muted size={12}>Visible seulement avec le droit « Voir l’origine des inscriptions ».</T>
    </Section>
  );
}

function Rows({ title, rows }: { title: string; rows: Count[] }) {
  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <T weight="semibold" style={{ flex: 1 }}>{title}</T>
        <T muted size={13} style={{ width: 64, textAlign: 'right' }}>30 jours</T>
        <T muted size={13} style={{ width: 52, textAlign: 'right' }}>Total</T>
      </View>
      {rows.map((r) => (
        <View key={r.label} style={{ flexDirection: 'row', gap: 8, paddingVertical: 4, borderTopWidth: 1, borderTopColor: colors.line }}>
          <T style={{ flex: 1 }}>{r.label}</T>
          <T weight="semibold" style={{ width: 64, textAlign: 'right', fontVariant: ['tabular-nums'] }}>{r.last30}</T>
          <T muted style={{ width: 52, textAlign: 'right', fontVariant: ['tabular-nums'] }}>{r.total}</T>
        </View>
      ))}
    </View>
  );
}

/** Admin › Membres : comptes par source et par plateforme, 30 derniers jours et total. Rien sans le droit. */
export function SignupOriginStats() {
  const { can } = useAuth();
  const allowed = can(SIGNUP_PERM);
  const { data } = useQuery(async () => {
    if (!allowed) return null;
    const { data, error } = await supabase.rpc('admin_signup_stats');
    return error ? null : ((data as Stats | null) ?? null);
  }, [allowed]);
  if (!data) return null;
  return (
    <Card style={{ gap: 14 }}>
      <T weight="semibold" size={17}>D’où viennent les inscrits</T>
      <Rows title="Source" rows={data.sources ?? []} />
      <Rows title="Plateforme" rows={data.platforms ?? []} />
      <T muted size={12}>Noté à l’inscription depuis le 22.11.2026 ; les comptes d’avant restent « Inconnu ».</T>
    </Card>
  );
}
