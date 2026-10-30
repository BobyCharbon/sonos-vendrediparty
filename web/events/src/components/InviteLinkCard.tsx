import { useState } from 'react';
import { Platform, Share, View } from 'react-native';

import { Button, ConfirmButton, ErrorText, Section, T } from './ui';
import { supabase } from '@/lib/supabase';

/** Adresse publique d'un lien d'invitation (le module Événements est servi sous /events sur le site de Party). */
export function inviteUrl(kind: 'event' | 'group', token: string): string {
  const origin = typeof location !== 'undefined' ? location.origin : 'https://party.bobycharbon.ch';
  return `${origin}/events/${kind === 'event' ? 'invite' : 'group-invite'}/${token}`;
}

/** Lien d'invitation d'un événement sur invitation ou d'un groupe : l'afficher, le copier, le partager, le renouveler
 * (l'ancien lien ne marche plus). Seuls les organisateurs / le créateur l'obtiennent (la base le vérifie). */
export function InviteLinkCard({ kind, id }: { kind: 'event' | 'group'; id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(renew = false) {
    setBusy(true);
    setError(null);
    const { data, error } = kind === 'event'
      ? await supabase.rpc('event_invite_link', { e: id, renew })
      : await supabase.rpc('group_invite_link', { grp: id, renew });
    setBusy(false);
    if (error || !data) return setError('Le lien n’a pas pu être créé. Réessaie.');
    setUrl(inviteUrl(kind, data as string));
    setNote(renew ? 'Nouveau lien créé : l’ancien ne marche plus.' : null);
  }

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setNote('Lien copié');
    } catch {
      setNote('Copie impossible : sélectionne le lien pour le copier.');
    }
  }

  async function share() {
    if (!url) return;
    try {
      if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
        await navigator.share({ title: 'Invitation Party', url });
      } else {
        await Share.share({ message: url });
      }
    } catch { /* partage annulé */ }
  }

  const who = kind === 'event'
    ? 'Qui l’ouvre s’inscrit avec son numéro, complète son profil, puis accède à cet événement seulement. Rien n’est visible avant. Tu es prévenu à chaque arrivée.'
    : 'Qui l’ouvre s’inscrit avec son numéro, complète son profil, puis rejoint ce groupe. Rien n’est visible avant. Tu es prévenu à chaque arrivée.';
  return (
    <Section title="Lien d’invitation">
      <T muted size={13}>{who}</T>
      {url ? (
        <>
          <T size={13} weight="semibold">{url}</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small label="Copier" style={{ flex: 1 }} onPress={() => void copy()} />
            <Button small variant="secondary" label="Partager" style={{ flex: 1 }} onPress={() => void share()} />
          </View>
          <ConfirmButton small label="Nouveau lien" confirmLabel="L’ancien ne marchera plus : confirmer" onConfirm={() => load(true)} />
        </>
      ) : (
        <Button small variant="secondary" label="Afficher le lien" loading={busy} onPress={() => void load()} />
      )}
      {note ? <T muted size={13}>{note}</T> : null}
      <ErrorText error={error} />
    </Section>
  );
}
