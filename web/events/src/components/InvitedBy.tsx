import { View } from 'react-native';

import { Section, T } from './ui';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { supabase } from '@/lib/supabase';

type InvitedBy = { inviter: string | null; via: 'app' | 'group' | 'event'; target_name: string | null; at: string };

/** « lien Party », « via le groupe X », « via l'événement Y ». */
export function invitedVia(row: Pick<InvitedBy, 'via' | 'target_name'>): string {
  if (row.via === 'group') return `via le groupe ${row.target_name ?? '(supprimé)'}`;
  if (row.via === 'event') return `via l’événement ${row.target_name ?? '(supprimé)'}`;
  return 'avec son lien Party';
}

/** Fiche d'un membre › « Invité par » : qui l'a fait venir, par quel lien, quand. Seulement avec le droit « Voir qui a
 * invité qui » (la base renvoie null sans lui) ; rien ne s'affiche pour les autres. */
export function InvitedBySection({ id }: { id: string }) {
  const { data } = useQuery(async () => {
    const { data, error } = await supabase.rpc('member_invited_by', { target: id });
    if (error) return null;
    return (data as InvitedBy[] | null) ?? null;
  }, [id]);
  if (!data?.length) return null;
  return (
    <Section title="Invité par">
      {data.map((row, i) => (
        <View key={`${row.via}-${row.at}-${i}`} style={{ gap: 2 }}>
          <T weight="semibold">{row.inviter || 'Compte supprimé'}</T>
          <T muted size={13}>{`${invitedVia(row)} · ${formatShort(row.at)}`}</T>
        </View>
      ))}
      <T muted size={12}>Visible seulement des admins (droit « Voir qui a invité qui »).</T>
    </Section>
  );
}
