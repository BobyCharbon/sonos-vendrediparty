import { useState } from 'react';
import { Platform, Pressable, Share, View } from 'react-native';

import { Button, ConfirmButton, ErrorText, Section, Segmented, T } from './ui';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

type Kind = 'event' | 'group';
type Mode = 'single' | 'reusable';
type LinkRow = { token: string; created_at: string; expires_at: string; used_at: string | null; used_by: string | null;
  status: 'pending' | 'used' | 'expired' | 'revoked' };

/** Adresse publique d'un lien d'invitation (le module Événements est servi sous /events sur le site de Party). */
export function inviteUrl(kind: Kind, token: string): string {
  const origin = typeof location !== 'undefined' ? location.origin : 'https://party.bobycharbon.ch';
  return `${origin}/events/${kind === 'event' ? 'invite' : 'group-invite'}/${token}`;
}

const STATUS: Record<LinkRow['status'], string> = { pending: 'En attente', used: 'Utilisé', expired: 'Expiré', revoked: 'Annulé' };

/** Liens d'invitation (avis n°9, précision du 30.10) :
 * - événement privé : liens UNIQUES seulement (une personne, une fois, 7 jours) — un lien par personne invitée ;
 * - groupe privé : lien unique (par défaut) ou lien réutilisable (renouvelable : l'ancien ne marche plus).
 * L'organisateur voit les liens créés et peut annuler ceux qui n'ont pas servi. La base vérifie chaque droit. */
export function InviteLinkCard({ kind, id }: { kind: Kind; id: string }) {
  const [mode, setMode] = useState<Mode>('single');
  return (
    <Section title="Lien d’invitation">
      {kind === 'group' ? (
        <Segmented options={[{ key: 'single', label: 'Lien unique' }, { key: 'reusable', label: 'Réutilisable' }]}
          value={mode} onChange={setMode} />
      ) : null}
      {mode === 'single' ? <SingleUseLinks kind={kind} id={id} /> : <ReusableLink id={id} />}
    </Section>
  );
}

function SingleUseLinks({ kind, id }: { kind: Kind; id: string }) {
  const [fresh, setFresh] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: links, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc('my_invite_links', { k: kind, target: id });
    if (error) throw new Error('Les liens créés n’ont pas pu être lus.');
    return (data as LinkRow[]) ?? [];
  }, [kind, id]);

  async function create() {
    setBusy(true);
    setError(null);
    const { data, error } = await supabase.rpc('create_invite_link', { k: kind, target: id });
    setBusy(false);
    if (error || !data) return setError(error?.message.replace(/^\w+: /, '') || 'Le lien n’a pas pu être créé. Réessaie.');
    setFresh(inviteUrl(kind, data as string));
    reload();
  }

  async function revoke(token: string) {
    const { error } = await supabase.rpc('revoke_invite_link', { tok: token });
    if (error) setError('Le lien n’a pas pu être annulé.');
    if (fresh?.endsWith(token)) setFresh(null);
    reload();
  }

  return (
    <View style={{ gap: 10 }}>
      <View style={{ padding: 12, borderRadius: radius.md, backgroundColor: colors.accentDim, gap: 4 }}>
        <T weight="bold" size={14}>🔒 Lien unique</T>
        <T size={13} color={colors.textSoft}>
          Il ne marche qu’une fois, pour une seule personne, pendant 7 jours. Crée un lien pour chaque personne que tu
          invites. Elle s’inscrit avec son numéro, complète son profil, puis {kind === 'event' ? 'accède à cet événement' : 'rejoint ce groupe'}.
          Tu es prévenu à son arrivée.
        </T>
      </View>
      {fresh ? <LinkActions url={fresh} /> : null}
      <Button small label={fresh ? 'Créer un autre lien unique' : 'Créer un lien unique'} loading={busy} onPress={() => void create()} />
      <ErrorText error={error} />
      {links?.length ? (
        <View style={{ gap: 6 }}>
          <T muted size={13} weight="semibold">Liens créés</T>
          {links.map((l) => (
            <View key={l.token} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <T size={13}>{l.status === 'used' ? `Utilisé par ${l.used_by ?? '?'}` : STATUS[l.status]}</T>
                <T muted size={12}>
                  Créé le {formatShort(l.created_at)}{l.status === 'pending' ? ` · expire le ${formatShort(l.expires_at)}` : ''}
                </T>
              </View>
              {l.status === 'pending' ? (
                <Pressable accessibilityRole="button" accessibilityLabel="Annuler ce lien" hitSlop={8} onPress={() => void revoke(l.token)}>
                  <T size={13} weight="semibold" color={colors.redSoft}>Annuler</T>
                </Pressable>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/** Groupe : lien réutilisable (tout le monde, jusqu'à ce qu'on le renouvelle). */
function ReusableLink({ id }: { id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(renew = false) {
    setBusy(true);
    setError(null);
    const { data, error } = await supabase.rpc('group_invite_link', { grp: id, renew });
    setBusy(false);
    if (error || !data) return setError('Le lien n’a pas pu être créé. Réessaie.');
    setUrl(inviteUrl('group', data as string));
  }

  return (
    <View style={{ gap: 10 }}>
      <T muted size={13}>
        Lien réutilisable : il marche pour tout le monde, jusqu’à ce que tu le renouvelles. Pratique pour une conversation
        de groupe ; chacun s’inscrit, complète son profil puis rejoint le groupe. Tu es prévenu à chaque arrivée.
      </T>
      {url ? (
        <>
          <LinkActions url={url} />
          <ConfirmButton small label="Nouveau lien" confirmLabel="L’ancien ne marchera plus : confirmer" onConfirm={() => load(true)} />
        </>
      ) : (
        <Button small variant="secondary" label="Afficher le lien réutilisable" loading={busy} onPress={() => void load()} />
      )}
      <ErrorText error={error} />
    </View>
  );
}

function LinkActions({ url }: { url: string }) {
  const [note, setNote] = useState<string | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setNote('Lien copié');
    } catch {
      setNote('Copie impossible : sélectionne le lien pour le copier.');
    }
  }

  async function share() {
    try {
      if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
        await navigator.share({ title: 'Invitation Party', url });
      } else {
        await Share.share({ message: url });
      }
    } catch { /* partage annulé */ }
  }

  return (
    <View style={{ gap: 8 }}>
      <T size={13} weight="semibold">{url}</T>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button small label="Copier" style={{ flex: 1 }} onPress={() => void copy()} />
        <Button small variant="secondary" label="Partager" style={{ flex: 1 }} onPress={() => void share()} />
      </View>
      {note ? <T muted size={13}>{note}</T> : null}
    </View>
  );
}
