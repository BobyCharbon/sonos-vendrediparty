import { router } from 'expo-router';
import { useRef, useState } from 'react';

import { Button, ErrorText, Field, Screen, Section, T } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { check, supabase } from '@/lib/supabase';

export default function AccountSettings() {
  const { profile } = useAuth();
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);

  async function removeAccount() {
    if (confirmation !== 'SUPPRIMER' || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      check(await supabase.rpc('delete_my_account'));
      await supabase.auth.signOut({ scope: 'local' });
      router.replace('/sign-in');
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      setError(message.includes('last_admin')
        ? 'Tu es le dernier administrateur. Dans Admin → Membres, désigne un autre administrateur actif puis réessaie.'
        : 'Ton compte n’a pas pu être supprimé. Vérifie ta connexion et réessaie.');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <Screen edges={[]}>
      <Section title="Supprimer mon compte">
        <T>Cette action est définitive. Ton profil, tes messages, tes votes, tes réponses et tes préférences seront supprimés.</T>
        <T>Les événements que tu as créés et leurs discussions seront également supprimés pour le groupe.</T>
        {profile?.role === 'admin' ? <T muted>Si tu es le dernier administrateur, désigne d’abord un autre administrateur dans la gestion des membres.</T> : null}
        <Field label="Écris SUPPRIMER pour confirmer" value={confirmation} onChangeText={setConfirmation} autoCapitalize="characters" autoCorrect={false} editable={!busy} maxLength={9} />
        <ErrorText error={error} />
        <Button variant="danger" label="Supprimer définitivement mon compte" loading={busy} disabled={confirmation !== 'SUPPRIMER'} onPress={removeAccount} />
        <Button variant="secondary" label="Garder mon compte" disabled={busy} onPress={() => router.canGoBack() ? router.back() : router.replace('/')} />
      </Section>
    </Screen>
  );
}
