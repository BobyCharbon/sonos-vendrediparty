import { useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';

import { Button, Card, ErrorText, Field, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { supabase } from '@/lib/supabase';

/** Choix du prénom puis attente de validation par un admin. */
export default function Welcome() {
  const { profile, refreshProfile, signOut } = useAuth();
  const [name, setName] = useState(profile?.display_name ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!profile) return;
    setBusy(true);
    setError(null);
    try {
      const { error } = await supabase.from('profiles').update({ display_name: name.trim() }).eq('id', profile.id);
      if (error) throw error;
      await refreshProfile();
    } catch {
      setError('Ton prénom n’a pas pu être enregistré. Réessaie en gardant cette page ouverte.');
    } finally {
      setBusy(false);
    }
  }

  const named = !!profile?.display_name.trim();

  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 20 }}>
      <Title size={32}>Bienvenue</Title>
      {profile?.status === 'banned' ? (
        <T muted>Ton accès a été retiré par un admin du groupe.</T>
      ) : (
        <>
          <View style={{ gap: 12 }}>
            <Field
              label="Ton prénom (visible par le groupe)"
              value={name}
              onChangeText={setName}
              autoComplete="given-name"
              maxLength={40}
            />
            <ErrorText error={error} />
            <Button label={named ? 'Mettre à jour' : 'Continuer'} onPress={save} loading={busy} disabled={!name.trim()} />
          </View>
          {named && profile?.status === 'pending' ? (
            <Card>
              <T weight="semibold">Demande envoyée</T>
              <T muted>Un admin doit valider ton accès. Tu pourras ensuite voir les événements du groupe.</T>
              <T muted size={13}>Cette page se met à jour automatiquement après validation.</T>
              <Button label="Vérifier à nouveau" variant="secondary" onPress={refreshProfile} />
            </Card>
          ) : null}
        </>
      )}
      <Button label="Se déconnecter" variant="ghost" onPress={signOut} />
      <Button label="Confidentialité" variant="ghost" onPress={() => router.push('/privacy')} />
      <Button label="Supprimer mon compte" variant="ghost" onPress={() => router.push('/settings/account')} />
    </Screen>
  );
}
