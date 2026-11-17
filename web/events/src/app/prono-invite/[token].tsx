import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { HonourNote } from '@/components/pronos/Bits';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { hasCompleteIdentity } from '@/lib/profile';
import { errorText, isTerms, openProno, rpc, type Face, type Prono } from '@/lib/pronos';
import { colors } from '@/lib/theme';

const TOKEN = /^[A-Za-z0-9_-]{20,40}$/;
type Info = { id: string; question: string; closes_at: string; creator: Face; joined: boolean; missing: 'profile' | 'terms' | null };

/**
 * Lien d'un prono (WhatsApp…) : sans compte, on se connecte d'abord (SMS) ; profil incomplet : prénom, nom, surnom ici ;
 * puis la question, et « Jouer » ajoute la personne au prono (CGU acceptées avant). La base revérifie tout.
 */
export default function PronoInvite() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { session, profile, refreshProfile } = useAuth();
  if (typeof token !== 'string' || !TOKEN.test(token)) return <Gone />;
  if (!session) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Stack.Screen options={{ title: 'Un prono pour toi' }} />
        <Text style={{ fontSize: 48 }}>🔮</Text>
        <Title size={30}>On t’invite à un prono</Title>
        <T muted>Pour le découvrir et jouer, connecte-toi à Party avec ton numéro de téléphone : un code te sera envoyé par SMS.</T>
        <Button label="M’inscrire ou me connecter" onPress={() => router.push('/sign-in')} />
      </Screen>
    );
  }
  if (!profile) return <Loading />;
  if (!hasCompleteIdentity(profile)) {
    return (
      <Screen contentStyle={{ gap: 20 }}>
        <Stack.Screen options={{ title: 'Un prono pour toi' }} />
        <Title size={30}>Faisons connaissance</Title>
        <T muted>Ton prénom, ton nom et ton surnom (une photo aussi, vivement conseillée), pour que les autres te reconnaissent.</T>
        <IdentityForm profile={profile} submitLabel="Continuer" onSaved={() => void refreshProfile()} />
      </Screen>
    );
  }
  return <Join token={token} />;
}

function Join({ token }: { token: string }) {
  const { data, error, loading } = useQuery(() => rpc<Info>('prono_link_info', { token }), [token]);
  const terms = useTermsGate('Avant de jouer');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = (id: string) => openProno(id, (path) => router.replace(path as never));

  async function join(): Promise<void> {
    setBusy(true);
    setErr(null);
    try {
      const p = await rpc<Prono>('prono_join', { token });
      go(p.id);
    } catch (e) {
      if (isTerms(e) && (await terms.ensure())) return join();
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading />;
  if (!data) return <Gone error={error} />;
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
      <Stack.Screen options={{ title: 'Un prono pour toi' }} />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Avatar id={data.creator.id} name={data.creator.name} photo={data.creator.avatar_url} size={40} profile={false} />
        <T muted style={{ flex: 1 }}>{data.creator.name} t’invite à un prono</T>
      </View>
      <Title size={30}>{data.question}</Title>
      <T muted>Les réponses restent cachées jusqu’au dévoilement. À jouer jusqu’au {formatShort(data.closes_at)}.</T>
      <HonourNote />
      <ErrorText error={err} />
      <Button label={data.joined ? 'Ouvrir le prono' : '🔮 Jouer'} loading={busy} onPress={() => (data.joined ? go(data.id) : void join())} />
      {terms.sheet}
    </Screen>
  );
}

function Gone({ error }: { error?: string | null }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Un prono pour toi' }} />
      <Title>Lien indisponible</Title>
      <T muted>Ce lien ne marche plus : les pronos sont fermés, ou l’organisateur a arrêté le lien.</T>
      {error ? <T size={13} color={colors.muted}>{error}</T> : null}
    </Screen>
  );
}
