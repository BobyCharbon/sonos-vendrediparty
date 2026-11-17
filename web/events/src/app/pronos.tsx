import { router, Stack } from 'expo-router';
import { useEffect } from 'react';
import { Text, View } from 'react-native';

import { goBack, PillButton, TopBar } from '@/components/agenda/Bits';
import { HonourNote, PronoCardView } from '@/components/pronos/Bits';
import { ErrorText, Loading, Screen, T } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { nativePronos, newProno, openProno, rpc, type PronoCard } from '@/lib/pronos';
import { colors } from '@/lib/theme';

/**
 * App « Pronos » (Réglages › Autres apps, 17.11) : tous mes pronos, de tous mes groupes, événements et invitations.
 * D'abord ce qui m'attend (résultat à donner, à jouer), puis ceux en cours, puis les terminés.
 */
export default function PronosHome() {
  const me = useMe();
  const native = nativePronos();
  useEffect(() => {
    if (native?.list) { native.list(); goBack('/account'); }
  }, [native]);
  const { data, error, loading, reload } = useQuery(() => rpc<PronoCard[]>('prono_list'), []);
  useSignal([`user:${me.id}`], reload);
  const push = (path: string) => router.push(path as never);
  const list = data ?? [];
  const todo = list.filter((p) => (p.state === 'closed' && p.mine) || (p.state === 'open' && !p.answered));
  const running = list.filter((p) => !todo.includes(p) && (p.state === 'open' || p.state === 'closed'));
  const over = list.filter((p) => p.state === 'done' || p.state === 'cancelled');

  return (
    <Screen contentStyle={{ gap: 12, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: 'Pronos' }} />
      <TopBar back="Réglages" fallback="/account" title="Pronos" subtitle="Devine, joue pour l’honneur, grimpe au classement."
        right={<PillButton label="＋ Nouveau" tone="accent" testID="prono-new" onPress={() => newProno({}, push)} />} />
      {loading && !data ? <Loading /> : null}
      <ErrorText error={error ?? null} />
      {data && !list.length ? (
        <View style={{ alignItems: 'center', gap: 8, padding: 24, borderRadius: 20, backgroundColor: colors.surface }}>
          <Text style={{ fontSize: 40 }}>🔮</Text>
          <T weight="bold" size={17}>Aucun prono pour l’instant</T>
          <T muted size={14} style={{ textAlign: 'center' }}>Lance le premier : « Qui arrive en dernier ? », « Le score du match ? »…
            Les réponses restent cachées jusqu’au dévoilement.</T>
        </View>
      ) : null}
      <Section title="À FAIRE" items={todo} push={push} />
      <Section title="EN COURS" items={running} push={push} />
      <Section title="TERMINÉS" items={over} push={push} />
      <HonourNote />
    </Screen>
  );
}

function Section({ title, items, push }: { title: string; items: PronoCard[]; push: (path: string) => void }) {
  if (!items.length) return null;
  return (
    <View style={{ gap: 10 }}>
      <T size={13} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8, marginTop: 6 }}>{title} · {items.length}</T>
      {items.map((p, i) => <PronoCardView key={p.id} p={p} index={i} onPress={() => openProno(p.id, push)} />)}
    </View>
  );
}
