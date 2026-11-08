import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ErrorText, Loading, T } from './ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { dbMessage } from '@/lib/moderation';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { DateVote } from '@/lib/types';

const CHOICES: { key: DateVote; label: string; color: string }[] = [
  { key: 'yes', label: 'Oui', color: colors.accent },
  { key: 'if_needed', label: 'Si besoin', color: colors.lavender },
  { key: 'no', label: 'Non', color: colors.coral },
];

type Option = { id: string; starts_at: string };

/**
 * Sondage de dates vu par un invité venu par un lien (retour de l'admin, 08.11) : les mêmes dates et les mêmes choix
 * que dans l'app (Oui, Si besoin, Non), enregistrés avec son compte léger. L'organisateur fixe ensuite la date qui
 * arrange le plus de monde ; chacun est alors inscrit selon son vote pour cette date.
 */
export function InviteDateVotes({ eventId, onVoted }: { eventId: string; onVoted: (count: number) => void }) {
  const { session } = useAuth();
  const me = session?.user.id ?? '';
  const [error, setError] = useState<string | null>(null);
  const [mine, setMine] = useState<Record<string, DateVote>>({});
  const { data, error: loadError } = useQuery(async () => {
    const options = must(await supabase.from('date_options').select('id, starts_at').eq('event_id', eventId).order('starts_at')) as Option[];
    const votes = options.length
      ? must(await supabase.from('date_votes').select('option_id, vote').eq('user_id', me).in('option_id', options.map((o) => o.id))) as { option_id: string; vote: DateVote }[]
      : [];
    setMine(Object.fromEntries(votes.map((v) => [v.option_id, v.vote])));
    onVoted(votes.length);
    return options;
  }, [eventId, me]);

  async function choose(option: string, vote: DateVote) {
    const before = mine;
    const next = { ...mine, [option]: vote };
    setMine(next);  // tout de suite à l'écran ; remis comme avant si la base refuse
    setError(null);
    const { error: refused } = await supabase.from('date_votes').upsert({ option_id: option, user_id: me, vote });
    if (refused) {
      setMine(before);
      return setError(dbMessage(refused.message, 'Ton vote n’a pas pu être enregistré. Réessaie.'));
    }
    onVoted(Object.keys(next).length);
  }

  if (!data) return loadError ? <ErrorText error={loadError} /> : <Loading />;
  if (!data.length) return <T muted>L’organisateur n’a pas encore proposé de dates. Rouvre ce lien un peu plus tard.</T>;
  return (
    <View style={{ gap: 10 }}>
      {data.map((o) => (
        <View key={o.id} style={st.row}>
          <T weight="bold" size={15}>{formatShort(o.starts_at)}</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {CHOICES.map((c) => {
              const on = mine[o.id] === c.key;
              return (
                <Pressable key={c.key} accessibilityRole="button" accessibilityState={{ selected: on }}
                  accessibilityLabel={`${c.label} : ${formatShort(o.starts_at)}`} onPress={() => void choose(o.id, c.key)}
                  style={[st.choice, { borderColor: on ? c.color : colors.lineStrong, backgroundColor: on ? c.color : 'transparent' }]}>
                  <T size={14} weight="bold" color={on ? colors.onAccent : colors.textSoft}>{c.label}</T>
                </Pressable>
              );
            })}
          </View>
        </View>
      ))}
      <ErrorText error={error} />
    </View>
  );
}

const st = StyleSheet.create({
  row: { gap: 8, padding: 14, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  choice: { flex: 1, minHeight: 44, borderRadius: radius.sm, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
});
