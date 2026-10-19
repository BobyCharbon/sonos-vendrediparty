import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Button, ErrorText, T, Title } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

type Announcement = { id: string; title: string; body: string; created_at: string };
const pageSize = 20;

export function Announcements({ compact = false }: { compact?: boolean }) {
  const [older, setOlder] = useState<Announcement[]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pagingError, setPagingError] = useState<string | null>(null);
  const { data, error, reload } = useQuery(async () => {
    const rows = must(await supabase.from('admin_announcements').select('id,title,body,created_at')
      .order('created_at', { ascending: false }).order('id', { ascending: false }).limit(compact ? 3 : pageSize + 1)) as Announcement[];
    setOlder([]);
    setMore(rows.length > pageSize);
    return rows;
  }, [compact]);
  const rows = [...(data?.slice(0, compact ? 3 : pageSize) ?? []), ...older];

  async function loadOlder() {
    const last = rows.at(-1);
    if (!last || busy) return;
    setBusy(true); setPagingError(null);
    try {
      const next = must(await supabase.from('admin_announcements').select('id,title,body,created_at')
        .or(`created_at.lt.${last.created_at},and(created_at.eq.${last.created_at},id.lt.${last.id})`)
        .order('created_at', { ascending: false }).order('id', { ascending: false }).limit(pageSize + 1)) as Announcement[];
      setOlder((previous) => [...previous, ...next.slice(0, pageSize)]);
      setMore(next.length > pageSize);
    } catch { setPagingError('Impossible de charger les annonces précédentes. Réessaie.'); }
    finally { setBusy(false); }
  }

  return (
    <View style={{ gap: 14 }}>
      {compact ? <Title size={20}>Annonces admin</Title> : null}
      <T muted size={13}>Pour tout le groupe. Les annonces restent accessibles après lecture et ne peuvent pas être masquées.</T>
      <ErrorText error={pagingError ?? error} />
      {error ? <Button label="Recharger les annonces" variant="secondary" onPress={reload} /> : null}
      {!data && !error ? <T muted>Chargement des annonces…</T> : null}
      {data?.length === 0 ? <T muted>Aucune annonce pour le moment.</T> : null}
      {rows.map((row) => (
        <View key={row.id} style={{ gap: 6, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.line }}>
          <T weight="bold" size={17}>{row.title}</T>
          <T>{row.body}</T>
          <T muted size={12}>Administration · {formatMessageTime(row.created_at)}</T>
        </View>
      ))}
      {compact ? <Button small label="Toutes les annonces" variant="ghost" onPress={() => router.push('/announcements')} /> : more ? (
        <Button label="Annonces précédentes" variant="secondary" loading={busy} onPress={loadOlder} />
      ) : null}
    </View>
  );
}
