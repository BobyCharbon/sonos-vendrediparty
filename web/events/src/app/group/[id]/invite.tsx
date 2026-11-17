import { Stack, useLocalSearchParams } from 'expo-router';

import { GroupInvitePanel } from '@/components/GroupInvite';
import { ErrorText, Loading, Screen } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { type GroupColor } from '@/lib/groups';
import { must, supabase } from '@/lib/supabase';

/** « Inviter » de la page du groupe : le même écran que l'étape 2 de la création (lien, code QR, personnes croisées). */
export default function GroupInvite() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, error, loading } = useQuery(async () => (must(await supabase.from('member_groups')
    .select('id, name, emoji, color, system_key').eq('id', id).maybeSingle()) as { id: string; name: string; emoji: string; color: GroupColor;
      system_key: string | null } | null), [id]);
  if (loading && !data) return <Loading />;
  return (
    <Screen edges={[]}>
      <Stack.Screen options={{ title: 'Inviter' }} />
      {data ? <GroupInvitePanel group={{ ...data, system: !!data.system_key }} /> : <ErrorText error={error ?? 'Ce groupe n’existe plus.'} />}
    </Screen>
  );
}
