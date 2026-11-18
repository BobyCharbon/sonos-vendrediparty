import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Card, Empty, ErrorText, LinkRow, Loading, RowDivider, Screen, Section, Segmented, T, ToggleRow } from '@/components/ui';
import { AI_CONSENT_TEXT, aiConsentLabel, aiConsentStatus, setAiConsent } from '@/lib/aiConsent';
import { useQuery } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { myBlocks, setBlocked, TERMS_PATH, useTerms } from '@/lib/moderation';
import { supabase } from '@/lib/supabase';

/** Réglages des Discussions (`public.chat_prefs`, soi seulement) : qui peut m'envoyer une demande de message,
 * confirmations de lecture réciproques (les couper = ne plus voir celles des autres). */
type ChatPrefs = { message_requests: 'all' | 'none'; read_receipts: boolean };

async function chatPrefs(): Promise<ChatPrefs | null> {
  if (!discussionsOn) return null;
  const { data, error } = await supabase.rpc('chat_prefs_get');
  if (error?.code === 'PGRST202') return null;  // base d'avant les Discussions v2 : pas de section
  if (error) throw new Error('Tes réglages des Discussions n’ont pas pu être lus.');
  return data as ChatPrefs;
}

/** Réglages › Confidentialité : personnes bloquées (blocage commun à toute l'app), conditions d'utilisation acceptées,
 * accord pour l'IA (pour TOUS les comptes : le voir, le retirer, le redonner), politique de confidentialité. */
export default function PrivacySettings() {
  const { data, loading, error, reload } = useQuery(myBlocks, []);
  const terms = useTerms();
  const ai = useQuery(aiConsentStatus, []);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const chat = useQuery(chatPrefs, []);

  async function setChat(patch: Partial<ChatPrefs>) {
    if (!chat.data || busy) return;
    setBusy('chat');
    setActionError(null);
    try {
      const { error: e } = await supabase.rpc('chat_prefs_set', patch);
      if (e) throw e;
      chat.setData({ ...chat.data, ...patch });
    } catch {
      setActionError('Ton réglage des Discussions n’a pas été enregistré. Vérifie ta connexion et réessaie.');
    } finally {
      setBusy(null);
    }
  }

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

  async function answerAi(accept: boolean) {
    setBusy('ai');
    setActionError(null);
    try {
      await setAiConsent(accept);
      await ai.reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Ton choix pour l’IA n’a pas été enregistré.');
    } finally {
      setBusy(null);
    }
  }

  const accepted = terms.status?.accepted;
  const aiAccepted = ai.data?.consent === 'accepted';
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
      {discussionsOn && (chat.loading || chat.data || chat.error) ? (
        <Section title="Discussions">
          {chat.loading && !chat.data ? <Loading /> : null}
          {chat.data ? (
            <>
              <T weight="semibold">Demandes de message</T>
              <T muted size={13}>Qui peut t’envoyer une demande quand vous n’avez pas de groupe ni d’événement privé en commun : un seul message texte, que tu acceptes ou non.</T>
              <Segmented<ChatPrefs['message_requests']> value={chat.data.message_requests} disabled={busy === 'chat'}
                onChange={(message_requests) => void setChat({ message_requests })}
                options={[{ key: 'all', label: 'Tout membre' }, { key: 'none', label: 'Personne' }]} />
              <T muted size={13}>{chat.data.message_requests === 'all'
                ? 'Tout membre peut t’envoyer une demande. Les personnes avec qui tu as un vrai lien t’écrivent toujours directement.'
                : 'Plus aucune demande. Seules les personnes avec qui tu as un vrai lien (groupe, événement privé, organisateur) peuvent t’écrire.'}</T>
              <ToggleRow disabled={busy === 'chat'} label="Confirmations de lecture"
                hint="Dans un message direct, l’autre voit « Vu » quand tu as lu. Si tu les coupes, tu ne vois plus celles des autres."
                value={chat.data.read_receipts} onChange={(read_receipts) => void setChat({ read_receipts })} />
            </>
          ) : null}
          <ErrorText error={chat.error} />
        </Section>
      ) : null}
      <Section title="Conditions d’utilisation">
        <T muted size={13}>{accepted ? `Acceptées${acceptedAt ? ` le ${acceptedAt}` : ''}.` : 'Pas encore acceptées : elles te seront demandées avant ton premier message ou ton premier nom.'}</T>
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <Button small variant="secondary" label="Lire les conditions" onPress={() => router.push(TERMS_PATH)} />
          {terms.status && !accepted ? <Button small label="J’ai 18 ans ou plus · J’accepte les conditions" onPress={() => void accept()} /> : null}
        </View>
      </Section>
      <Section title="IA de Party">
        {ai.loading && !ai.data ? <Loading /> : null}
        {ai.data ? <T muted size={13}>{aiConsentLabel(ai.data)}</T> : null}
        {ai.data && !aiAccepted ? <T muted size={13}>{AI_CONSENT_TEXT}</T> : null}
        {ai.data ? (
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {aiAccepted
              ? <Button small variant="secondary" label="Retirer mon accord" loading={busy === 'ai'} onPress={() => void answerAi(false)} />
              : <Button small label="J’accepte" loading={busy === 'ai'} onPress={() => void answerAi(true)} />}
          </View>
        ) : null}
        <T muted size={13}>Sans accord, tout marche sans l’IA. Un seul accord pour toute l’IA de Party (Ton avis, assistant des événements, tickets).</T>
        <ErrorText error={ai.error} />
      </Section>
      <ErrorText error={actionError} />
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <LinkRow icon="🔒" tint="#0A84FF" label="Politique de confidentialité" hint="Tes données et leur conservation" onPress={() => router.push('/privacy')} />
      </Card>
    </Screen>
  );
}
