import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, View } from 'react-native';

import { PickedChip, QrOverlay, ResultRow, st } from './InviteSheet';
import { inviteUrl } from './InviteLinkCard';
import { usePersonText } from './PersonName';
import { SheetBackdrop, SheetClose, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, Input, T, Toast } from './ui';
import { useQuery } from '@/lib/data';
import { copyText, openMessages, openWhatsApp, shareInvite } from '@/lib/invites';
import { pressTransition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

type Person = { id: string; display_name: string; avatar_url: string | null };
const RESULTS_SHOWN = 12;

/**
 * « + Ajouter » d'un groupe (avis de l'admin du 14.11) : la même feuille que « Inviter » d'un événement.
 * En haut, des gens de Party (recherche par surnom ou nom du répertoire, jamais un numéro) : chacun reçoit une
 * invitation (invite_to_group, notification « invitation dans un groupe », son interrupteur) et entre dès qu'il accepte.
 * Dessous, le lien du groupe (réutilisable) pour quelqu'un qui n'a pas encore l'app : Partager, WhatsApp, Messages, QR, Copier.
 * Mêmes droits qu'aujourd'hui (base : private.manages_group, jamais Vendredi Party).
 */
export function GroupAddSheet({ visible, group, me, people, inside, onClose, onDone }: {
  visible: boolean; group: { id: string; name: string }; me: { id: string; display_name: string };
  people: Person[]; inside: Set<string>; onClose: () => void; onDone: () => void;
}) {
  const personText = usePersonText();
  const [search, setSearch] = useState('');
  const [picked, setPicked] = useState<Person[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [qr, setQr] = useState(false);
  const inviting = useRef(false);
  const sheetRef = useRef<View>(null);
  const scrollRef = useRef<ScrollView>(null);
  const qrRef = useRef<View>(null);
  useSheetDrag(visible, onClose, sheetRef, scrollRef);
  useSheetDrag(visible && qr, () => setQr(false), qrRef);
  const top = useSheetTop();

  const { data: url, error: linkError } = useQuery(async () => {
    if (!visible) return null;
    const { data, error: failed } = await supabase.rpc('group_invite_link', { grp: group.id, renew: false });
    if (failed || !data) throw new Error('Le lien n’a pas pu être créé. Réessaie.');
    return inviteUrl('group', data as string);
  }, [visible, group.id]);

  const host = me.display_name.trim() || 'Moi';
  const message = (link: string) => `Hello ! ${host} t’invite dans le groupe « ${group.name} » sur Party. Rejoins-le ici : ${link}`;
  const name = (p: Person) => personText(p.id, p.display_name);
  const q = search.trim().toLowerCase().replace(/^@/, '');
  const matches = q ? people.filter((p) => p.id !== me.id && (p.display_name.toLowerCase().includes(q) || name(p).toLowerCase().includes(q))) : [];
  const found = matches.filter((p) => !picked.some((x) => x.id === p.id)).slice(0, RESULTS_SHOWN);
  const names = picked.map(name);

  async function send(how: 'share' | 'whatsapp' | 'sms' | 'copy' | 'qr') {
    if (!url) return;
    if (how === 'whatsapp') openWhatsApp(message(url));
    else if (how === 'sms') openMessages(message(url));
    else if (how === 'qr') setQr(true);
    else if (how === 'copy') setNote((await copyText(url)) ? 'Lien copié' : 'Copie impossible : touche le lien pour le sélectionner');
    else if ((await shareInvite(message(url), url, group.name)) === 'copied') setNote('Message copié : colle-le où tu veux');
  }

  /** Une invitation par personne choisie : elle entre dans le groupe dès qu'elle accepte (jamais d'office). */
  async function invite() {
    if (inviting.current || !picked.length) return;
    inviting.current = true;
    setBusy(true);
    setError(null);
    const done: string[] = [];
    try {
      for (const p of picked) {
        const { error: failed } = await supabase.rpc('invite_to_group', { grp: group.id, member: p.id, phone: null });
        if (failed) throw new Error(`${name(p)} : ${failed.message.replace(/^\w+: /, '')}`);
        done.push(p.id);
      }
      setNote(`${names.join(', ')} : invitation envoyée. ${picked.length > 1 ? 'Ils entrent' : 'Il entre'} dans le groupe dès ${picked.length > 1 ? 'qu’ils acceptent' : 'qu’il accepte'}.`);
      setSearch('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'L’invitation n’a pas pu partir. Réessaie.');
    } finally {
      setPicked((list) => list.filter((p) => !done.includes(p.id)));
      inviting.current = false;
      setBusy(false);
      if (done.length) onDone();
    }
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} aria-label={`Ajouter au groupe ${group.name}`}>
      <View style={[st.overlay, { paddingTop: top }]}>
        <SheetBackdrop onPress={onClose} />
        <View ref={sheetRef} style={st.sheet} accessibilityViewIsModal testID="group-add-sheet">
          <View style={st.grabber} />
          <View style={st.head}>
            <View style={{ flex: 1 }}>
              <T weight="bold" size={20} numberOfLines={1}>Ajouter au groupe</T>
              <T muted size={13} numberOfLines={1}>« {group.name} »</T>
            </View>
            <SheetClose onPress={onClose} />
          </View>
          <ScrollView ref={scrollRef} contentContainerStyle={{ gap: 18, paddingBottom: 32 }} keyboardShouldPersistTaps="handled">
            {/* 1. Des gens déjà sur Party */}
            <View style={{ gap: 10 }}>
              <T weight="bold" size={17}>Des gens de Party</T>
              <Input accessibilityLabel="Chercher une personne" placeholder="🔍 Un prénom, un surnom…" value={search} onChangeText={setSearch} />
              {picked.length ? (
                <View style={st.chips}>
                  {picked.map((p) => <PickedChip key={p.id} label={name(p)} onRemove={() => setPicked(picked.filter((x) => x.id !== p.id))} />)}
                </View>
              ) : null}
              {found.map((p) => (
                <ResultRow key={p.id} title={name(p)} person={p} disabled={inside.has(p.id)}
                  hint={inside.has(p.id) ? 'Déjà dans le groupe' : 'Sur Party'} onPress={() => setPicked([...picked, p])} />
              ))}
              {q && !matches.length ? (
                <Pressable accessibilityRole="button" disabled={!url} onPress={() => void send('share')} style={st.notFound}>
                  <T size={14} weight="semibold">« {search.trim()} » n’est pas sur Party ?</T>
                  <T size={13} color={colors.accent} weight="semibold">Envoie-lui le lien du groupe ›</T>
                </Pressable>
              ) : null}
              {picked.length ? <Button label={`Inviter ${names.join(', ')}`} loading={busy} onPress={() => void invite()} /> : null}
              <ErrorText error={error} />
              <T muted size={12}>Chacun reçoit une notification Party et entre dans le groupe dès qu’il accepte (Réglages › Groupes).</T>
            </View>

            {/* 2. Le lien du groupe, pour qui n'a pas encore l'app */}
            <View style={st.linkCard}>
              <T weight="bold" size={17}>🔗 Pas encore sur Party ?</T>
              <T size={13} color={colors.textSoft}>Envoie le lien du groupe : la personne s’inscrit avec son numéro, complète son profil et rejoint « {group.name} ». Tu es prévenu à chaque arrivée.</T>
              {url ? <T size={12} muted numberOfLines={1}>{url.replace(/^https?:\/\//, '')}</T> : linkError ? <ErrorText error={linkError} /> : <T muted size={12}>Préparation du lien…</T>}
              <Button label="Partager le lien…" disabled={!url} onPress={() => void send('share')} />
              <View style={st.shareRow}>
                {([['whatsapp', '💬', 'WhatsApp'], ['sms', '✉︎', 'Messages'], ['qr', '▦', 'QR code'], ['copy', '⧉', 'Copier']] as const).map(([k, icon, l]) => (
                  <Pressable key={k} accessibilityRole="button" accessibilityLabel={l} disabled={!url} onPress={() => void send(k)}
                    style={({ pressed }) => [st.shareBtn, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
                    <T size={20}>{icon}</T>
                    <T size={12} weight="semibold" color={colors.textSoft}>{l}</T>
                  </Pressable>
                ))}
              </View>
            </View>
          </ScrollView>
        </View>
        {qr && url ? (
          <QrOverlay cardRef={qrRef} url={url} title={group.name} when={null} caption="👥 Lien du groupe"
            hint="La personne vise le code avec l’appareil photo, s’inscrit et rejoint le groupe." onClose={() => setQr(false)} />
        ) : null}
        {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
      </View>
    </Modal>
  );
}
