import { useRef, useState } from 'react';
import { View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { PROFILE_PHOTOS, uploadProfilePhoto } from '@/lib/photos';
import { NICKNAME_MAX, hasCompleteIdentity } from '@/lib/profile';
import { check, supabase } from '@/lib/supabase';
import type { Profile } from '@/lib/types';
import { dbMessage } from '@/lib/moderation';
import { ProfilePhotoField } from './ProfilePhotoField';
import { useTermsGate } from './TermsSheet';
import { Button, ErrorText, Field, T } from './ui';

/** Surnom déjà choisi dans les jeux de Party (même origine) : il pré-remplit un profil qui n'en a pas encore, coupé à la
 * limite du surnom (un nom de jeu plus long était refusé par la base au premier essai). */
function gameNickname(): string {
  try { return typeof localStorage === 'undefined' ? '' : (localStorage.getItem('vp_name') ?? '').trim().slice(0, NICKNAME_MAX).trim(); } catch { return ''; }
}

/** « Écris ton prénom et ton surnom pour continuer. » : les champs obligatoires encore vides. */
function missingText(identity: { first_name: string; last_name: string; display_name: string }): string {
  const missing = [!identity.first_name && 'ton prénom', !identity.last_name && 'ton nom', !identity.display_name && 'ton surnom'].filter(Boolean) as string[];
  const list = missing.length > 1 ? `${missing.slice(0, -1).join(', ')} et ${missing[missing.length - 1]}` : missing[0];
  return `Écris ${list} pour continuer.`;
}

/** Nom, prénom (privés), surnom (public) et photo sur une seule page, pour bien voir la différence. */
export function IdentityForm({ profile, submitLabel, onSaved }: { profile: Profile; submitLabel: string; onSaved?: () => void }) {
  const { refreshProfile } = useAuth();
  const [firstName, setFirstName] = useState(profile.first_name ?? '');
  const [lastName, setLastName] = useState(profile.last_name ?? '');
  const [nickname, setNickname] = useState(() => profile.display_name || gameNickname());
  const [photo, setPhoto] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const saving = useRef(false);
  // Le surnom est vu de tous : conditions d'utilisation acceptées avant le premier nom (modération commune).
  const terms = useTermsGate('Avant de commencer');
  const identity = { first_name: firstName.trim(), last_name: lastName.trim(), display_name: nickname.trim(), avatar_url: photo ?? profile.avatar_url };
  const changed = !!photo || identity.first_name !== (profile.first_name ?? '') || identity.last_name !== (profile.last_name ?? '') || identity.display_name !== profile.display_name;

  async function save() {
    if (saving.current || !hasCompleteIdentity(identity)) return;
    // Garde posée AVANT l'attente des CGU : un double toucher pendant cette attente n'enregistre pas deux fois.
    saving.current = true;
    if (identity.display_name !== profile.display_name && !terms.accepted && !(await terms.ensure())) {
      saving.current = false;
      return;
    }
    setBusy(true);
    setError(null);
    let uploaded: string | null = null;
    try {
      if (photo) uploaded = await uploadProfilePhoto(profile.id, photo);
      check(await supabase.from('profiles').update({ ...identity, avatar_url: uploaded ?? profile.avatar_url }).eq('id', profile.id).select('id').single());
      if (uploaded && profile.avatar_url) await supabase.storage.from(PROFILE_PHOTOS).remove([profile.avatar_url]).catch(() => {});
      await refreshProfile();
      setPhoto(null);
      setSaved(true);
      onSaved?.();
    } catch (e) {
      if (uploaded) await supabase.storage.from(PROFILE_PHOTOS).remove([uploaded]).catch(() => {});
      const fallback = 'Tes informations n’ont pas pu être enregistrées. Vérifie ta connexion puis réessaie.';
      // Filtre de la base : « Ce texte n'est pas accepté : il contient une insulte… » (surnom refusé).
      setError(e instanceof Error ? (/^(content_refused|terms_required|nickname_too_long): /.test(e.message) ? dbMessage(e.message, fallback) : e.message) : fallback);
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: 14 }}>
      {terms.sheet}
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Field label="Prénom" value={firstName} onChangeText={(v) => { setFirstName(v); setSaved(false); }} autoComplete="given-name" autoCapitalize="words" maxLength={100} editable={!busy} />
        </View>
        <View style={{ flex: 1 }}>
          <Field label="Nom" value={lastName} onChangeText={(v) => { setLastName(v); setSaved(false); }} autoComplete="family-name" autoCapitalize="words" maxLength={100} editable={!busy} />
        </View>
      </View>
      <T muted size={13}>🔒 Ton prénom et ton nom ne sont visibles que par toi et les admins.</T>
      <Field label="Surnom" hint={`👀 Ce que tout le monde voit : jeux, événements, discussions. ${nickname.length} / ${NICKNAME_MAX}`} value={nickname} onChangeText={(v) => { setNickname(v); setSaved(false); }} maxLength={NICKNAME_MAX} editable={!busy} />
      <ProfilePhotoField userId={profile.id} name={nickname} currentPhoto={profile.avatar_url} photo={photo} onChange={(uri) => { setPhoto(uri); setSaved(false); }} disabled={busy} />
      <ErrorText error={error} />
      {saved && !changed ? <T size={14} weight="semibold">✓ Enregistré</T> : null}
      {/* Bouton grisé : dire ce qui manque (recette UX du 14.11, rien n'expliquait pourquoi « Continuer » ne répondait pas). */}
      {!hasCompleteIdentity(identity) ? <T muted size={13} style={{ textAlign: 'center' }}>{missingText(identity)}</T> : null}
      {changed || !hasCompleteIdentity(profile) ? (
        <Button label={submitLabel} onPress={save} loading={busy} disabled={!hasCompleteIdentity(identity)} />
      ) : null}
    </View>
  );
}
