import { router } from 'expo-router';
import { Pressable, View } from 'react-native';

import { Button, Empty, ErrorText, Screen, T, Title } from '@/components/ui';
import { Announcements } from '@/components/Announcements';
import { useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

type Item = { id: string; title: string; body: string; event_id: string | null; created_at: string; read_at: string | null };

/** Historique des notifications reçues (les mêmes que les push). */
export default function Activity() {
  const me = useMe();
  const { data, error, reload } = useQuery(async () => {
    const res = await supabase
      .from('notifications')
      .select('id, title, body, event_id, created_at, read_at')
      .neq('kind', 'admin_announcement')
      .order('created_at', { ascending: false })
      .limit(100);
    return must(res) as Item[];
  }, [me.id]);

  async function open(n: Item) {
    if (!n.read_at) await supabase.from('notifications').update({ read_at: new Date().toISOString() }).eq('id', n.id);
    if (n.event_id) router.push(`/event/${n.event_id}`);
    else reload();
  }

  async function markAll() {
    await supabase.from('notifications').update({ read_at: new Date().toISOString() }).is('read_at', null);
    reload();
  }

  const unread = data?.filter((n) => !n.read_at).length ?? 0;

  return (
    <Screen>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title>Activité</Title>
        {unread ? <Button small variant="ghost" label="Tout marquer lu" onPress={markAll} /> : null}
      </View>
      <ErrorText error={error} />
      <Announcements compact />
      <Title size={20}>Notifications des événements</Title>
      {data?.length === 0 ? <Empty>Aucune notification pour l’instant.</Empty> : null}
      {data?.map((n) => (
        <Pressable
          key={n.id}
          accessibilityRole="button"
          onPress={() => open(n)}
          style={{
            flexDirection: 'row', gap: 12, padding: 14, borderRadius: radius.md,
            backgroundColor: n.read_at ? 'transparent' : colors.surface,
          }}
        >
          <View style={{ width: 8, height: 8, borderRadius: 4, marginTop: 7, backgroundColor: n.read_at ? 'transparent' : colors.accent }} />
          <View style={{ flex: 1, gap: 2 }}>
            <T weight="semibold">{n.title}</T>
            <T muted size={14}>{n.body}</T>
            <T muted size={12}>{formatMessageTime(n.created_at)}</T>
          </View>
        </Pressable>
      ))}
    </Screen>
  );
}
