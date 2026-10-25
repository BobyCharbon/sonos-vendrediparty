import { useState } from 'react';
import { View } from 'react-native';

import { Button, ErrorText, Input, T } from './ui';
import { check, supabase } from '@/lib/supabase';

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/** Suppression complète d'un compte (Root, Admin) : on tape son surnom pour confirmer. Irréversible ; la personne
 * pourra se réinscrire par SMS et repartira Guest. Le serveur revérifie tout (rang, surnom) et journalise. */
export function DeleteMember({ id, name, onDeleted }: { id: string; name: string; onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return <Button small variant="danger" label="Supprimer le compte" onPress={() => setOpen(true)} />;

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      check(await supabase.rpc('admin_delete_member', { member: id, confirm_name: typed }));
      onDeleted();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message.includes('confirm') ? 'Le surnom tapé ne correspond pas.'
        : message.includes('forbidden') ? 'Tu ne peux supprimer qu’un compte d’un rôle inférieur au tien.'
        : message.replace(/^\w+: /, ''));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: 8, width: '100%' }}>
      <T size={14}>Tout sera effacé : profil, photo, numéro, réponses, messages. Tape « {name || '?'} » pour confirmer.</T>
      <Input value={typed} onChangeText={setTyped} placeholder={name} accessibilityLabel={`Surnom de ${name} pour confirmer`} autoCapitalize="none" editable={!busy} />
      <ErrorText error={error} />
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button small variant="secondary" label="Annuler" disabled={busy} style={{ flex: 1 }} onPress={() => { setOpen(false); setTyped(''); setError(null); }} />
        <Button small variant="dangerSolid" label="Supprimer définitivement" loading={busy} disabled={!name || !same(typed, name)} style={{ flex: 1 }} onPress={remove} />
      </View>
    </View>
  );
}
