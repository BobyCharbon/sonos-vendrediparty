import { router, type Href } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { Label, PillButton, TopBar } from '@/components/agenda/Bits';
import { LinkCard } from '@/components/agenda/LinkEditor';
import { Button, ErrorText, Screen, Skeleton, T } from '@/components/ui';
import { MODELS, rpc, type Links } from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { enter, pressTransition } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';

/**
 * Mes liens de dispo (maquettes 6A, 7D) : un lien montre à quelqu'un hors de Party quand je suis disponible, sans compte et
 * sans voir mes rendez-vous. 10 au plus, 90 jours, « Prolonger », « Arrêter » (rallumé à la même adresse), vues pour moi
 * seul ; les demandes de rendez-vous en attente sur chaque lien (pastille en temps réel, signal user:<id>).
 */
export default function LinksScreen() {
  const me = useMe();
  const { data, error, reload } = useQuery(() => rpc<Links>('agenda_links'), []);
  useSignal([`user:${me.id}`], reload);
  const full = !!data && data.links.length >= data.max;

  return (
    <Screen>
      <TopBar back="Calendriers" fallback="/agenda/calendars" title="Mes liens de dispo"
        right={data?.links.length ? <PillButton label="+ Nouveau lien" tone="accent" testID="links-new" onPress={() => router.push('/agenda/links/new' as Href)} /> : null}
        subtitle={data?.links.length ? `${data.links.length} lien${data.links.length > 1 ? 's' : ''} sur ${data.max} · nombre de vues visible par toi seulement` : undefined} />
      <ErrorText error={error} />
      {!data && !error ? <Skeleton height={200} radius={radius.lg} /> : null}
      {data?.missing === 'profile' ? (
        <View style={st.missing}>
          <T size={15} weight="bold">Complète ton profil pour créer un lien</T>
          <T muted size={14}>Prénom, nom et surnom : la personne voit seulement le nom que tu choisis.</T>
          <Button small variant="secondary" label="Compléter mon profil" onPress={() => router.push('/settings/profile' as Href)} />
        </View>
      ) : null}
      {full ? <T muted size={13}>Tu as déjà {data!.max} liens. Supprimes-en un pour en créer un autre.</T> : null}

      {data && !data.links.length ? (
        <View style={{ gap: 12 }}>
          <View style={[st.empty, enter('fade')]}>
            <View style={st.icon}><T size={30}>🔗</T></View>
            <T size={20} weight="bold" style={{ textAlign: 'center' }}>Aucun lien pour l’instant</T>
            <T size={15} color={colors.textSoft} style={{ textAlign: 'center' }}>Un lien montre à quelqu’un hors de Party (un client, ton coach…) quand tu es disponible. Sans compte, sans voir tes rendez-vous.</T>
          </View>
          <Label>Commence par un modèle</Label>
          <View style={st.models}>
            {MODELS.map((m, i) => (
              <Pressable key={m.key} accessibilityRole="button" accessibilityLabel={`${m.name}, ${m.hint}`} testID={`empty-model-${m.key}`}
                onPress={() => router.push(`/agenda/links/new?model=${m.key}` as Href)}
                style={({ pressed }) => [st.model, enter('rise', i), pressTransition, pressed && { opacity: 0.85 }]}>
                <T size={22}>{m.emoji}</T>
                <T size={15} weight="bold">{m.name}</T>
                <T muted size={12}>{m.hint}</T>
              </Pressable>
            ))}
          </View>
          <Button label="Créer un lien" onPress={() => router.push('/agenda/links/new' as Href)} />
        </View>
      ) : null}

      {data?.links.map((l, i) => <LinkCard key={l.id} link={l} index={i} onChanged={reload} />)}
    </Screen>
  );
}

const st = StyleSheet.create({
  missing: { gap: 8, padding: 14, borderRadius: radius.lg, backgroundColor: colors.lavenderDim },
  empty: { alignItems: 'center', gap: 10, padding: 22, borderRadius: radius.lg, borderWidth: 1.5, borderStyle: 'dashed', borderColor: colors.lineStrong },
  icon: { width: 64, height: 64, borderRadius: 18, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center',
    shadowColor: colors.accent, shadowOpacity: 0.5, shadowRadius: 18 },
  models: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  model: { flexBasis: '47%', flexGrow: 1, gap: 2, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface },
});
