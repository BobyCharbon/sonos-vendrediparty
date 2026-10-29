import { Redirect, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Button, Empty, ErrorText, Screen, Section, T } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { check, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { roleLabel, type MemberRole } from '@/lib/types';

type Entry = { id: number; at: string; action: string; actor: string | null; actor_name: string | null; target: string | null; target_name: string | null; details: Record<string, unknown> | null };

const PAGE = 100;
const role = (r: unknown) => roleLabel[r as MemberRole] ?? String(r ?? '?');
const status = (s: unknown) => ({ active: 'actif', banned: 'accès retiré', pending: 'en attente' } as Record<string, string>)[String(s)] ?? String(s ?? '?');

/** Phrase lisible pour une ligne du journal : « Boby a passé Tom de Guest à Membre VIP ». */
function describe(e: Entry): string {
  const who = e.actor_name || (e.actor ? 'Compte supprimé' : 'Système');
  const target = e.target_name || (e.target ? 'compte supprimé' : '');
  const d = e.details ?? {};
  switch (e.action) {
    case 'account.created': return `${target || 'Nouveau compte'} a créé son compte`;
    case 'account.login': return `${target || 'Un compte'} s’est connecté${d.device ? ` (${String(d.device).slice(0, 40)})` : ''}`;
    case 'account.deleted': return d.by === 'self' ? `${target} a supprimé son compte` : `${who} a supprimé le compte de ${target}${d.phone_end ? ` (numéro …${d.phone_end})` : ''}`;
    case 'member.role': return `${who} a passé ${target} de ${role(d.from)} à ${role(d.to)}`;
    case 'member.status': return `${who} : ${target} ${status(d.from)} → ${status(d.to)}`;
    case 'member.beta': return `${who} a ${d.enabled ? 'ajouté' : 'retiré'} ${target} ${d.enabled ? 'aux' : 'des'} bêta-testeurs`;
    case 'group.add': return `${who} a ajouté ${target} au groupe « ${d.group ?? '?'} »`;
    case 'group.remove': return `${who} a retiré ${target} du groupe « ${d.group ?? '?'} »`;
    case 'members.viewed': return `${who} a ouvert la liste des membres (numéros compris)`;
    default: return `${who} : ${e.action}${target ? ` · ${target}` : ''}`;
  }
}

/** Journal des membres (Root, Admin) : tout, ou celui d'un membre (?member=…). Lecture seule. */
export default function Journal() {
  const { rank } = useAuth();
  const { member, name } = useLocalSearchParams<{ member?: string; name?: string }>();
  const [older, setOlder] = useState<Entry[]>([]);
  const [olderError, setOlderError] = useState<string | null>(null);
  const [lastPage, setLastPage] = useState(PAGE);
  const { data, error, loading, reload } = useQuery(async () => {
    const res = await supabase.rpc('admin_member_audit', { member: member ?? null, before: null, lim: PAGE });
    check(res);
    setOlder([]);
    const rows = (res.data ?? []) as Entry[];
    setLastPage(rows.length);
    return rows;
  }, [member]);

  if (rank < 4) return <Redirect href="/" />;
  const entries = [...(data ?? []), ...older];
  const done = lastPage < PAGE;

  async function loadOlder() {
    setOlderError(null);
    try {
      const res = await supabase.rpc('admin_member_audit', { member: member ?? null, before: entries[entries.length - 1]?.id ?? null, lim: PAGE });
      check(res);
      const rows = (res.data ?? []) as Entry[];
      setLastPage(rows.length);
      setOlder((list) => [...list, ...rows]);
    } catch (e) {
      setOlderError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Screen edges={[]}>
      <T muted size={14}>{member ? `Tout ce qui concerne ${name || 'ce membre'}.` : 'Inscriptions, connexions, rôles, bêta, groupes, accès retirés, suppressions et consultations de la liste.'} Rien n’y est modifiable.</T>
      <ErrorText error={error ?? olderError} />
      {error ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
      {loading && !data ? <T muted>Chargement du journal…</T> : null}
      <Section title={`Journal (${entries.length}${done ? '' : '+'})`}>
        {data && !entries.length ? <Empty>Rien dans le journal pour l’instant.</Empty> : null}
        {entries.map((e) => (
          <View key={e.id} accessibilityLabel="Ligne du journal" style={{ paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.line, gap: 2 }}>
            <T size={15}>{describe(e)}</T>
            <T muted size={12}>{formatMessageTime(e.at)}</T>
          </View>
        ))}
      </Section>
      {entries.length && !done ? <Button label="Plus ancien" variant="secondary" onPress={loadOlder} /> : null}
    </Screen>
  );
}
