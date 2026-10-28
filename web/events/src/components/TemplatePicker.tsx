import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { useQuery } from '@/lib/data';
import { createTemplate, deleteTemplate, listTemplates, type EventTemplate } from '@/lib/templates';
import { colors } from '@/lib/theme';
import { Button, ErrorText, Field, s, Section, T, ToggleRow } from './ui';

type Props = {
  meId: string;
  /** Admin ou co-admin : peut supprimer les modèles d'équipe des autres. */
  canDeleteAll: boolean;
};

/** Haut du formulaire (nouvel événement) : repartir d'un modèle perso 👤 ou d'équipe 👥. */
export function TemplateList({ meId, canDeleteAll, onApply }: Props & { onApply: (t: EventTemplate) => void }) {
  const { data, error, reload } = useQuery(listTemplates, []);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [applied, setApplied] = useState<string | null>(null);

  if (!data?.length && !error) return null;

  async function remove(t: EventTemplate) {
    if (confirming !== t.id) return setConfirming(t.id);
    setConfirming(null);
    setDeleteError(null);
    try {
      await deleteTemplate(t.id);
      await reload();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : 'Le modèle n’a pas pu être supprimé.');
    }
  }

  return (
    <Section title="Partir d’un modèle">
      <ErrorText error={error ?? deleteError} />
      {(data ?? []).map((t) => {
        const mine = t.owner_id === meId;
        const removable = mine || (canDeleteAll && t.shared);
        return (
          <View key={t.id} style={[s.row, { gap: 10 }]}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Remplir avec le modèle ${t.name}`}
              onPress={() => { onApply(t); setApplied(t.name); }}
              style={({ pressed }) => [s.card, { flex: 1, paddingVertical: 12, gap: 2 }, pressed && { backgroundColor: colors.surface2 }]}
            >
              <T weight="semibold">{t.shared ? '👥' : '👤'} {t.name}</T>
              <T muted size={12}>{t.shared ? (mine ? 'Équipe · le tien' : 'Équipe') : 'Perso'}</T>
            </Pressable>
            {removable ? (
              <Button small variant={confirming === t.id ? 'dangerSolid' : 'danger'}
                label={confirming === t.id ? 'Supprimer ?' : '🗑'} onPress={() => remove(t)} />
            ) : null}
          </View>
        );
      })}
      {applied ? <T size={13} color={colors.accent}>✓ « {applied} » appliqué : choisis la date, puis publie.</T> : null}
      <T muted size={12}>👥 modèle d’équipe, visible par tous les organisateurs · 👤 modèle perso, visible par toi seul.</T>
    </Section>
  );
}

/** Bas du formulaire : enregistrer les réglages actuels (sans dates ni personnes) comme modèle. */
export function SaveAsTemplate({ data }: { data: () => Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [shared, setShared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  if (!open) return (
    <View style={{ gap: 6 }}>
      <Button label="Enregistrer comme modèle" variant="secondary" onPress={() => { setOpen(true); setSaved(null); }} />
      {saved ? <T size={13} color={colors.accent}>✓ Modèle « {saved} » enregistré</T> : null}
    </View>
  );

  async function save() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await createTemplate(name, shared, data());
      setSaved(name.trim());
      setName('');
      setOpen(false);
    } catch {
      setError('Le modèle n’a pas pu être enregistré. Vérifie ta connexion puis réessaie.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Nouveau modèle">
      <T muted size={13}>Garde ces réglages pour les prochains événements : titre, description, catégorie, lieu, prix, places, sondages… Les dates et les personnes invitées ne sont pas gardées.</T>
      <Field label="Nom du modèle" value={name} onChangeText={setName} maxLength={60} placeholder="Raclette du vendredi, karting…" />
      <ToggleRow label="Pour toute l’équipe" hint="Visible par tous les organisateurs et admins. Sinon, pour toi seul." value={shared} onChange={setShared} />
      <ErrorText error={error} />
      <Button label="Enregistrer le modèle" onPress={save} loading={busy} disabled={!name.trim()} />
      <Button label="Annuler" variant="ghost" onPress={() => setOpen(false)} disabled={busy} />
    </Section>
  );
}
