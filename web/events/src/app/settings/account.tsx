import { router } from 'expo-router';
import { useRef, useState } from 'react';

import { Button, ErrorText, Field, Screen, Section, T } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { supabase } from '@/lib/supabase';

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
      // Par le serveur Party : la base (delete_my_account) ET ses fichiers à lui (stats de jeux, journal de l'IA,
      // accords, Zicou…) partent ensemble, comme depuis l'app iPhone (app/account_data.py).
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) throw new Error('Ta connexion a expiré : reconnecte-toi puis réessaie.');
      const response = await fetch('/api/account/delete', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, confirm: confirmation }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { detail?: unknown };
        throw new Error(typeof body.detail === 'string' ? body.detail : '');
      }
      await supabase.auth.signOut({ scope: 'local' });
      router.replace('/sign-in');
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      setError(message || 'Ton compte n’a pas pu être supprimé. Vérifie ta connexion et réessaie.');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <Screen edges={[]}>
      <Section title="Supprimer mon compte">
        <T>Cette action est définitive. Ton profil, tes messages, tes votes, tes réponses, tes préférences, tes stats de jeux et tes accords pour l’IA seront supprimés.</T>
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
