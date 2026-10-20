import { useState } from 'react';
import { View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { hasCompleteIdentity } from '@/lib/profile';
import { check, supabase } from '@/lib/supabase';
import { Button, Card, ErrorText, Input, T } from './ui';

type Request = { message: string | null; status: 'pending' | 'accepted' | 'refused'; created_at: string };

/** Invité : demande à rejoindre le groupe (accès aux sorties), avec un petit mot facultatif pour les admins. */
export function JoinRequest() {
  const { profile, refreshProfile } = useAuth();
  const { data, loading, reload } = useQuery(async () => {
    if (!profile) return null;
    const { data: row } = await supabase.from('join_requests').select('message, status, created_at').eq('user_id', profile.id).maybeSingle();
    return (row as Request | null) ?? null;
  }, [profile?.id, profile?.role]);
  const request = data;
  const [note, setNote] = useState<string | null>(null);  // null : reprend le message enregistré
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const text = note ?? request?.message ?? '';

  async function run(action: () => PromiseLike<{ error: { message: string } | null }>) {
    setBusy(true);
    setError(null);
    try {
      check(await action());
      setEditing(false);
      setNote(null);
      await reload();
      await refreshProfile();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message.includes('profile_incomplete') ? 'Complète d’abord ton profil : prénom, nom, surnom et photo.' : message);
    } finally {
      setBusy(false);
    }
  }

  if (!profile || profile.role !== 'guest' || (loading && request === null)) return null;
  const complete = hasCompleteIdentity(profile);
  const send = () => run(() => supabase.rpc('request_join', { note: text }));

  if (request?.status === 'pending' && !editing) {
    return (
      <Card>
        <T weight="semibold">Demande envoyée ✓</T>
        <T muted>Un admin va la regarder. Tu verras les sorties dès qu’elle est acceptée ; cette page se met à jour toute seule.</T>
        {request.message ? <T size={14}>« {request.message} »</T> : null}
        <ErrorText error={error} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          <Button small variant="secondary" label={request.message ? 'Modifier mon message' : 'Ajouter un message'} disabled={busy} onPress={() => setEditing(true)} />
          <Button small variant="ghost" label="Annuler la demande" disabled={busy} onPress={() => run(() => supabase.rpc('cancel_join_request'))} />
        </View>
      </Card>
    );
  }

  return (
    <Card>
      <T weight="semibold">Rejoindre le groupe</T>
      <T muted>{request?.status === 'refused'
        ? 'Ta dernière demande n’a pas été acceptée. Tu peux en refaire une, avec un mot pour te présenter.'
        : 'Pour voir les sorties, répondre et discuter avec le groupe, demande à le rejoindre. Les jeux et la musique restent ouverts sans attendre.'}</T>
      <Input
        value={text}
        onChangeText={setNote}
        placeholder="Un mot pour les admins (facultatif) : « C’est Léa, la copine de Tom 👋 »"
        accessibilityLabel="Message pour les admins (facultatif)"
        multiline
        maxLength={500}
        style={{ minHeight: 72, textAlignVertical: 'top' }}
        editable={!busy}
      />
      {!complete ? <T muted size={13}>Complète d’abord ton profil (prénom, nom, surnom et photo) : les admins doivent pouvoir te reconnaître.</T> : null}
      <ErrorText error={error} />
      <Button label={request?.status === 'pending' ? 'Enregistrer le message' : 'Demander à rejoindre'} loading={busy} disabled={!complete} onPress={send} />
      {editing ? <Button variant="ghost" label="Annuler" disabled={busy} onPress={() => { setEditing(false); setNote(null); }} /> : null}
    </Card>
  );
}
