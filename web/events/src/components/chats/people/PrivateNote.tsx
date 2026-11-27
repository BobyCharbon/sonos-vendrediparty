import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';

import { ConfirmButton } from '@/components/ui';
import { supabase } from '@/lib/supabase';

import { K, txt, web } from './bits';

export const NOTE_MAX = 500;

/** Ma note privée sur cette personne (avis ede29a5bb24e) : lue et écrite par moi seul (RLS de member_notes). */
async function readNote(target: string): Promise<string> {
  const { data, error } = await supabase.rpc('member_note_get', { target });
  if (error) throw new Error('Ta note n’a pas pu être lue.');
  return (data as { body?: string } | null)?.body ?? '';
}

async function saveNote(target: string, body: string): Promise<string> {
  const { data, error } = await supabase.rpc('member_note_set', { target, body });
  if (error) throw new Error('Ta note n’a pas pu être enregistrée. Réessaie.');
  return (data as { body?: string } | null)?.body ?? '';
}

/**
 * Bloc « 📝 Ma note privée » du profil d'une personne (mini-profil, fiche) : « où on s'est rencontrés… », 500 caractères,
 * modifiable et effaçable. Visible par moi seul : jamais montrée à la personne, ni partagée.
 */
export function PrivateNote({ userId, name, style }: { userId: string; name: string; style?: object }) {
  const [saved, setSaved] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let live = true;
    readNote(userId).then((n) => { if (live) { setSaved(n); setDraft(n); } }, () => { /* base sans notes : pas de bloc */ });
    return () => { live = false; };
  }, [userId]);

  if (saved === null) return null;
  const dirty = draft.trim() !== saved;

  async function store(next: string) {
    setBusy(true); setError(null);
    try {
      const n = await saveNote(userId, next);
      setSaved(n); setDraft(n); setDone(true);
      setTimeout(() => setDone(false), 1600);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ta note n’a pas pu être enregistrée.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="private-note" style={[{ marginHorizontal: 20, marginTop: 20, padding: 14, borderRadius: 18, gap: 10,
      backgroundColor: K.glass, borderWidth: 1, borderColor: K.glassLine }, style]}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text accessibilityRole="header" style={txt(15, '700', K.t1, 20)}>📝 Ma note privée</Text>
        <Text style={txt(12, '600', K.lav, 16)}>🔒 Visible par toi seul</Text>
      </View>
      <TextInput testID="private-note-input" accessibilityLabel={`Ma note privée sur ${name}`} value={draft} onChangeText={setDraft}
        multiline maxLength={NOTE_MAX} placeholder={`Où tu as rencontré ${name}, un détail à retenir…`} placeholderTextColor={K.t3}
        style={[txt(15, '400', K.t1, 21), web({ minHeight: 72, padding: 12, borderRadius: 14, backgroundColor: 'rgba(0,0,0,0.22)',
          borderWidth: 1, borderColor: K.line2, textAlignVertical: 'top' })]} />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={[txt(12, '400', K.t3, 16), { flex: 1 }]}>{draft.length}/{NOTE_MAX}{done ? ' · Enregistrée ✓' : ''}</Text>
        {saved && !dirty ? (
          // Règle de l'admin : tout effacement demande une confirmation (contrôle final, comme PrivateNoteCard sur iPhone).
          <ConfirmButton small label="Effacer" confirmLabel="Oui, effacer ma note" accessibilityLabel="Effacer ma note"
            onConfirm={() => void store('')} />
        ) : null}
        {dirty ? (
          <Pressable testID="private-note-save" accessibilityRole="button" disabled={busy} onPress={() => void store(draft)}
            style={({ pressed }) => [{ minHeight: 44, paddingHorizontal: 16, borderRadius: 14, justifyContent: 'center', backgroundColor: K.pink },
              pressed && { opacity: 0.8 }]}>
            {busy ? <ActivityIndicator color={K.onPink} /> : <Text style={txt(15, '700', K.onPink)}>Enregistrer</Text>}
          </Pressable>
        ) : null}
      </View>
      {error ? <Text accessibilityRole="alert" style={txt(13, '400', K.danger, 18)}>{error}</Text> : null}
    </View>
  );
}
