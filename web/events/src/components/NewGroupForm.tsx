import { useState } from 'react';
import { View } from 'react-native';

import { Button, ErrorText, Input, s } from './ui';
import { useMe } from '@/lib/auth';
import { supabase } from '@/lib/supabase';
import { dbMessage } from '@/lib/moderation';

type Props = {
  /** Le créateur fait partie du groupe d'office, comme Créateur · Admin (la base l'ajoute aussi : group_creator_joins). */
  join?: boolean;
  autoFocus?: boolean;
  onCreated: (id: string) => void;
};

/** Nouveau groupe : le même formulaire dans Réglages › Groupes et dans Discussions ; son créateur en fait partie. */
export function NewGroupForm({ join = true, autoFocus = false, onCreated }: Props) {
  const me = useMe();
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    const clean = name.trim();
    if (!clean || busy) return;
    setBusy(true);
    setError(null);
    const { data: created, error } = await supabase.from('member_groups').insert({ name: clean, created_by: me.id }).select('id').single();
    if (error || !created) {
      setBusy(false);
      // Nom refusé par le filtre de la base (modération commune) : la phrase dit pourquoi.
      return setError(dbMessage(error?.message, 'Le groupe n’a pas été créé. Réessaie.'));
    }
    const id = created.id as string;
    if (join) {
      const { error: joinError } = await supabase.from('member_group_members').insert({ group_id: id, user_id: me.id });
      if (joinError && !joinError.message.includes('duplicate')) {
        setBusy(false);
        return setError('Le groupe est créé, mais tu n’as pas pu y être ajouté. Ajoute-toi dans Réglages › Groupes.');
      }
    }
    setBusy(false);
    setName('');
    onCreated(id);
  }

  return (
    <View style={{ gap: 8 }}>
      <View style={s.row}>
        <Input accessibilityLabel="Nom du groupe" placeholder="Ex. Les footeux" value={name} onChangeText={setName} maxLength={60}
          style={{ flex: 1 }} onSubmitEditing={() => void create()} autoFocus={autoFocus} />
        <Button small label="Créer" disabled={!name.trim()} loading={busy} onPress={() => void create()} />
      </View>
      <ErrorText error={error} />
    </View>
  );
}
