import { useState } from 'react';

import { IdentityForm } from '@/components/IdentityForm';
import { ErrorText, Screen, Section, T, ToggleRow } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';

type Privacy = { show_name: boolean; phone_groups: string[] };

/** Réglages → Mon profil : prénom, nom, surnom et photo (ouvert depuis la carte du compte, comme sur iPhone),
 * et le choix de montrer son nom et prénom sur sa fiche profil (caché par défaut). */
export default function Profile() {
  const { profile } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const { data: privacy, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc('my_privacy');
    if (error) throw new Error(error.message);
    return data as Privacy;
  }, []);
  if (!profile) return null;

  async function showName(visible: boolean) {
    setError(null);
    const { error } = await supabase.rpc('set_name_public', { visible });
    if (error) setError('Ton choix n’a pas été enregistré. Réessaie.');
    await reload();
  }

  return (
    <Screen edges={[]}>
      <T muted size={14}>Ton surnom et ta photo te suivent dans les jeux et les événements.</T>
      <IdentityForm profile={profile} submitLabel="Enregistrer" />
      <Section title="Ma fiche profil">
        <ToggleRow
          label="Afficher mon nom et prénom"
          hint="Visibles par tous les comptes sur ta fiche (en touchant ta photo). Sinon, seuls toi et les admins les voient."
          value={!!privacy?.show_name}
          disabled={!privacy}
          onChange={(v) => void showName(v)}
        />
        <ErrorText error={error} />
        <T muted size={13}>Ton numéro reste caché : tu peux le montrer groupe par groupe (Réglages → Groupes).</T>
      </Section>
    </Screen>
  );
}
