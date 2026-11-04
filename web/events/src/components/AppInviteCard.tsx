import { useState } from 'react';
import { Linking, Platform, Pressable, Share, View } from 'react-native';

import { Button, ConfirmButton, ErrorText, Section, T, Toast } from './ui';
import { joinUrl, readable, shareTargets, shareText, type MyInvite } from '@/lib/appInvite';
import { useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

/** Réglages › Inviter dans Party (avis 84fab3987f68) : mon lien personnel, à partager partout (WhatsApp, Instagram,
 * Snapchat, Messages…) ; le NOMBRE de personnes arrivées grâce à lui (qui a invité qui : admins seulement).
 * Le lien ne donne aucun droit (les nouveaux arrivent en Guest). Le renouveler remplace l'ancien. */
export function AppInviteCard() {
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const invite = useQuery(async () => {
    const { data, error } = await supabase.rpc('my_app_invite', { renew: false });
    if (error) throw new Error(readable(error.message, 'Ton lien n’a pas pu être créé.'));
    return data as MyInvite;
  }, []);
  const url = invite.data ? joinUrl(invite.data.token) : null;
  const joined = invite.data?.joined ?? 0;

  /** Feuille de partage du téléphone (iPhone, Android) ; sinon le menu de repli. */
  async function share() {
    if (!url) return;
    if (Platform.OS !== 'web') {
      await Share.share({ message: shareText(url) }).catch(() => undefined);
      return;
    }
    if (typeof navigator !== 'undefined' && 'share' in navigator) {
      try {
        await navigator.share({ title: 'Party', text: 'Rejoins-moi sur Party, pour nos soirées et événements', url });
        return;
      } catch (e) {
        if ((e as Error)?.name === 'AbortError') return;  // partage annulé
      }
    }
    setMenu((open) => !open);
  }

  async function copy(message = 'Lien copié') {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setNote(message);
    } catch {
      setError('Copie impossible : sélectionne le lien pour le copier.');
    }
  }

  async function renew() {
    setError(null);
    const { error } = await supabase.rpc('my_app_invite', { renew: true });
    if (error) return setError(readable(error.message, 'Le nouveau lien n’a pas pu être créé.'));
    invite.reload();
    setNote('Nouveau lien prêt');
  }

  return (
    <Section title="Inviter dans Party">
      <T muted size={14}>
        Partage ton lien personnel sur WhatsApp, Instagram, Snapchat ou par message : tes amis s’inscrivent avec leur
        numéro et arrivent sur Party. Tu es prévenu à chaque arrivée.
      </T>
      {url ? (
        <View style={{ gap: 8 }}>
          <T size={13} weight="semibold">{url}</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {/* Icône de partage d'iOS (carré et flèche), comme partout sur l'iPhone. */}
            <Button small label="⬆︎ Partager" style={{ flex: 1 }} onPress={() => void share()} />
            <Button small variant="secondary" label="Copier" style={{ flex: 1 }} onPress={() => void copy()} />
          </View>
          {menu ? <ShareMenu url={url} onCopy={() => void copy('Lien copié : colle-le dans Instagram ou Snapchat')} /> : null}
          <ConfirmButton small label="Nouveau lien" confirmLabel="L’ancien ne marchera plus : confirmer" onConfirm={renew} />
        </View>
      ) : invite.loading ? null : <ErrorText error={invite.error} />}
      {joined ? (
        <T muted size={13}>{joined === 1 ? '1 personne a rejoint Party grâce à toi' : `${joined} personnes ont rejoint Party grâce à toi`}</T>
      ) : null}
      <ErrorText error={error} />
      {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
    </Section>
  );
}

/** Repli sans feuille de partage : liens directs (WhatsApp, Telegram, SMS, e-mail) et copie pour Instagram / Snapchat. */
function ShareMenu({ url, onCopy }: { url: string; onCopy: () => void }) {
  return (
    <View accessibilityRole="menu" style={{ borderRadius: radius.md, backgroundColor: colors.surface2, paddingVertical: 4 }}>
      {shareTargets(url).map((target) => (
        <Pressable key={target.key} accessibilityRole="menuitem" accessibilityLabel={`Partager par ${target.label}`}
          onPress={() => void Linking.openURL(target.href)} style={{ paddingVertical: 10, paddingHorizontal: 14 }}>
          <T>{target.label}</T>
        </Pressable>
      ))}
      <Pressable accessibilityRole="menuitem" accessibilityLabel="Copier pour Instagram ou Snapchat" onPress={onCopy}
        style={{ paddingVertical: 10, paddingHorizontal: 14 }}>
        <T>Instagram, Snapchat… : copier le lien</T>
        <T muted size={12}>Ces applis n’acceptent pas de lien direct : colle-le dans un message ou une story.</T>
      </Pressable>
    </View>
  );
}
