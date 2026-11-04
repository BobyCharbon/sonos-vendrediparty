import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Card, Empty, ErrorText, LinkRow, Loading, RowDivider, Screen, Section, T } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { myBlocks, setBlocked, TERMS_PATH, useTerms } from '@/lib/moderation';

/** Réglages › Confidentialité : personnes bloquées (blocage commun à toute l'app), conditions d'utilisation acceptées,
 * politique de confidentialité. */
export default function PrivacySettings() {
  const { data, loading, error, reload } = useQuery(myBlocks, []);
  const terms = useTerms();
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function unblock(id: string) {
    setBusy(id);
    setActionError(null);
    try {
      await setBlocked(id, false);
      await reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Le déblocage n’a pas pu être enregistré.');
    } finally {
      setBusy(null);
    }
  }

  async function accept() {
    setActionError(null);
    try {
      await terms.accept();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'L’acceptation n’a pas été enregistrée.');
    }
  }

  const accepted = terms.status?.accepted;
  const acceptedAt = terms.status?.accepted_at ? new Date(terms.status.accepted_at).toLocaleDateString('fr-CH') : null;
  return (
    <Screen edges={[]}>
      <Section title="Personnes bloquées">
        <T muted size={13}>Elles ne peuvent plus t’écrire, te citer, t’inviter ni voir ta fiche. Elles n’en sont pas prévenues.</T>
        {loading && !data ? <Loading /> : null}
        {data && !data.length ? <Empty>Personne n’est bloqué.</Empty> : null}
        {data?.length ? (
          <Card style={{ gap: 0, paddingVertical: 4 }}>
            {data.map((p, i) => (
              <View key={p.id}>
                {i ? <RowDivider /> : null}
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 }}>
                  <Avatar id={p.id} name={p.display_name || '?'} photo={p.avatar_url} size={40} profile={false} />
                  <T weight="semibold" style={{ flex: 1 }}>{p.display_name || 'Profil à compléter'}</T>
                  <Button small variant="secondary" label="Débloquer" loading={busy === p.id} onPress={() => void unblock(p.id)} />
                </View>
              </View>
            ))}
          </Card>
        ) : null}
        <ErrorText error={error} />
      </Section>
      <Section title="Conditions d’utilisation">
        <T muted size={13}>{accepted ? `Acceptées${acceptedAt ? ` le ${acceptedAt}` : ''}.` : 'Pas encore acceptées : elles te seront demandées avant ton premier message ou ton premier nom.'}</T>
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <Button small variant="secondary" label="Lire les conditions" onPress={() => router.push(TERMS_PATH)} />
          {terms.status && !accepted ? <Button small label="J’accepte les conditions" onPress={() => void accept()} /> : null}
        </View>
      </Section>
      <ErrorText error={actionError} />
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <LinkRow icon="🔒" tint="#0A84FF" label="Politique de confidentialité" hint="Tes données et leur conservation" onPress={() => router.push('/privacy')} />
      </Card>
    </Screen>
  );
}
