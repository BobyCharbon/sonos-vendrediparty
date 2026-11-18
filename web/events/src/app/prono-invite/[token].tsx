import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { GlassCard, PrimaryButton, Seal } from '@/components/pronos/Kit';
import { C, rounded } from '@/components/pronos/play/model';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { enter } from '@/lib/motion';
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
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 18 }}>
      <Stack.Screen options={{ title: 'Un prono pour toi' }} />
      <View style={[{ alignItems: 'center' }, enter('pop')]}><Seal emoji="🔮" size={104} /></View>
      <View style={st.from}>
        <Avatar id={data.creator.id} name={data.creator.name} photo={data.creator.avatar_url} size={36} profile={false} />
        <Text style={st.help} numberOfLines={2}>{data.creator.name} t’invite à un prono</Text>
      </View>
      <Text role="heading" aria-level={1} style={[rounded(30), { textAlign: 'center', lineHeight: 34 }]}>{data.question}</Text>
      <GlassCard style={st.card}>
        <Text style={st.line}>🔒  Les réponses restent scellées jusqu’à la fin : personne ne les voit, pas même {data.creator.name}.</Text>
        <Text style={st.line}>⏱  À jouer jusqu’au {formatShort(data.closes_at)}.</Text>
        <Text style={st.line}>🏅  Pour l’honneur : des points au classement, rien d’autre.</Text>
      </GlassCard>
      <ErrorText error={err} />
      <PrimaryButton label={data.joined ? 'Ouvrir le prono' : '🔮 Jouer'} loading={busy} onPress={() => (data.joined ? go(data.id) : void join())} />
      {terms.sheet}
    </Screen>
  );
}

const st = StyleSheet.create({
  from: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  help: { color: C.t2, fontSize: 15, flexShrink: 1 },
  card: { gap: 12, padding: 18, borderRadius: 24 },
  line: { color: C.t1, fontSize: 15, lineHeight: 21 },
});

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
