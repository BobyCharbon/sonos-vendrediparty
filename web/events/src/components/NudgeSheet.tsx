import { useEffect, useRef, useState } from 'react';
import { Modal, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, T } from './ui';
import {
  copyText, inviteLinkUrl, inviteMessage, nudgeInvitees, openMessages, openWhatsApp, shareInvite, type Guest,
} from '@/lib/invites';
import { colors, radius } from '@/lib/theme';

/** confirm : « Relancer les N » (un geste, puis une confirmation) ; sinon la relance d'une ligne part aussitôt. */
export type NudgeRequest = { people: Guest[]; confirm: boolean };
/** notified : combien la base a prévenus ; names : qui, quand c'est sûr (tous ceux envoyés l'ont été). */
type Done = { notified: number; names: Guest[] | null; skipped: number; share: Guest[]; marked: boolean };

const names = (people: Guest[]) => {
  const shown = people.slice(0, 4).map((p) => p.name);
  return people.length > 4 ? `${shown.join(', ')} et ${people.length - 4} autre${people.length - 4 > 1 ? 's' : ''}` : shown.join(', ');
};

/**
 * Relancer ceux qui n'ont pas répondu (demande de l'admin, 19.11) : ceux qui reçoivent les notifications de Party (app
 * iPhone ou webapp) sont prévenus par la base (nudge_invitees, une relance par jour) ; les autres reçoivent le lien par
 * la feuille de partage du téléphone, WhatsApp, Messages ou la copie, avec un message prêt. Chaque partage part d'un
 * toucher dans cette fenêtre (Safari et l'app iPhone refusent navigator.share après une attente du réseau).
 */
export function NudgeSheet({ request, event, host, when, onClose, onMarked }: {
  request: NudgeRequest | null; event: { id: string; title: string }; host: string; when: string | null;
  onClose: (changed: boolean) => void;
  /** Partage parti, relance notée par la base : la liste se relit (sinon le bouton restait jusqu'au rechargement). */
  onMarked: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Done | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  const people = request?.people ?? [];
  const reachable = people.filter((p) => p.has_app);
  const withoutApp = people.filter((p) => !p.has_app);

  function close() {
    const changed = !!done;
    setDone(null);
    setError(null);
    setNote(null);
    setBusy(false);
    onClose(changed);
  }
  useSheetDrag(!!request, close, card, overlay);

  // Seuls ceux qui reçoivent les notifications partent à la base : les autres ne sont notés « relancés » qu'au partage.
  async function send() {
    setBusy(true);
    setError(null);
    try {
      const result = reachable.length ? await nudgeInvitees(event.id, reachable.map((p) => p.id)) : { notified: 0, skipped: 0, share: [] };
      const toShare = [...withoutApp, ...reachable.filter((p) => result.share.includes(p.id))];
      const sent = reachable.filter((p) => !result.share.includes(p.id));
      setDone({ notified: result.notified, names: sent.length === result.notified ? sent : null, skipped: result.skipped, share: toShare, marked: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  // Relance d'une ligne : pas de question, elle part au toucher.
  useEffect(() => {
    if (!request || request.confirm || done || busy || error) return;
    const t = setTimeout(() => void send(), 0);  // hors du rendu de l'effet (règle set-state-in-effect)
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request]);

  const shareTo = done?.share ?? [];
  const single = shareTo.length === 1 ? shareTo[0]! : null;
  const url = single?.link_token ? inviteLinkUrl(single.link_token)
    : `${typeof location !== 'undefined' ? location.origin : 'https://party.bobycharbon.ch'}/events/event/${event.id}`;
  const text = inviteMessage({ name: single?.name ?? null, host, title: event.title, when, url, nudge: true });

  /** Après un partage : notés « relancés » aujourd'hui (une relance par jour), sans attendre (le partage est déjà parti). */
  function marked(message: string | null) {
    if (message) setNote(message);
    if (!done || done.marked) return;
    setDone({ ...done, marked: true });
    const ids = shareTo.filter((p) => !reachable.some((r) => r.id === p.id)).map((p) => p.id);
    if (ids.length) void nudgeInvitees(event.id, ids).then(onMarked, () => undefined);
  }

  async function share(how: 'share' | 'whatsapp' | 'sms' | 'copy') {
    if (how === 'whatsapp') return marked((openWhatsApp(text), null));
    if (how === 'sms') return marked((openMessages(text), null));
    if (how === 'copy') return (await copyText(text)) ? marked('Message copié : colle-le dans WhatsApp ou Messages') : setNote('Copie impossible : réessaie');
    const result = await shareInvite(text, url, event.title);
    if (result === 'shared') marked(null);
    else if (result === 'copied') marked('Message copié : colle-le dans WhatsApp ou Messages');
  }

  const canShare = typeof navigator !== 'undefined' && 'share' in navigator;
  const label = request?.confirm ? 'Relancer les invités sans réponse' : 'Relance';

  return (
    <Modal visible={!!request} transparent animationType="fade" onRequestClose={close}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={close} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel={label}>
          <SheetTop onClose={close} />
          {!done ? (
            <>
              <T weight="bold" size={20}>
                {people.length === 1 ? `Relancer ${people[0]!.name} ?` : `Relancer ${people.length} personnes ?`}
              </T>
              <T muted size={13}>{names(people)}</T>
              {reachable.length ? (
                <View style={st.line}>
                  <T size={18}>🔔</T>
                  <View style={{ flex: 1, gap: 2 }}>
                    <T size={14} weight="bold">{people.length === 1 ? 'Une notification de Party' : `${reachable.length} avec Party : une notification`}</T>
                    <T muted size={13}>« Invitation de {host} · Tu viens ? Réponds en un geste. »</T>
                  </View>
                </View>
              ) : null}
              {withoutApp.length ? (
                <View style={st.line}>
                  <T size={18}>💬</T>
                  <View style={{ flex: 1, gap: 2 }}>
                    <T size={14} weight="bold">{people.length === 1 ? 'Pas de notification possible' : `${withoutApp.length} sans l’app`}</T>
                    <T muted size={13}>{withoutApp.length > 1 ? 'Tu leur envoies' : 'Tu lui envoies'} le lien juste après (WhatsApp, Messages…).</T>
                  </View>
                </View>
              ) : null}
              <T muted size={12}>Une relance par jour et par personne.</T>
              <ErrorText error={error} />
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={close} />
                <Button label={busy ? 'Envoi…' : 'Relancer'} accessibilityLabel="Confirmer la relance" style={{ flex: 1 }} loading={busy}
                  onPress={() => void send()} />
              </View>
            </>
          ) : (
            <>
              <T weight="bold" size={20}>{done.notified ? 'C’est parti ✓' : shareTo.length ? 'Envoie-leur le lien' : 'Rien à relancer'}</T>
              {done.notified ? (
                <View style={st.line}>
                  <T size={18}>🔔</T>
                  <View style={{ flex: 1, gap: 2 }}>
                    <T size={15} weight="bold" color={colors.mint}>{done.notified === 1 && done.names ? `${done.names[0]!.name} est prévenu dans Party`
                      : `${done.notified} ${done.notified > 1 ? 'prévenus' : 'prévenu'} dans Party`}</T>
                    {done.notified > 1 && done.names ? <T muted size={13}>{names(done.names)}</T> : null}
                  </View>
                </View>
              ) : null}
              {shareTo.length ? (
                <View style={[st.line, st.shareBox]}>
                  <T size={18}>💬</T>
                  <View style={{ flex: 1, gap: 8 }}>
                    <View style={{ gap: 2 }}>
                      <T size={15} weight="bold">{single ? `${single.name} n’a pas l’app : envoie-lui le lien` : `${shareTo.length} sans l’app : partage-leur le lien`}</T>
                      {single ? null : <T muted size={13}>{names(shareTo)}</T>}
                    </View>
                    <View style={st.preview}><T size={13} color={colors.textSoft}>{text}</T></View>
                    {canShare ? <Button label="Partager le message…" onPress={() => void share('share')} /> : null}
                    <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
                      <Button small variant="secondary" label="WhatsApp" style={st.grow} onPress={() => void share('whatsapp')} />
                      <Button small variant="secondary" label="Messages" style={st.grow} onPress={() => void share('sms')} />
                      <Button small variant="secondary" label="Copier" accessibilityLabel="Copier le message" style={st.grow} onPress={() => void share('copy')} />
                    </View>
                  </View>
                </View>
              ) : null}
              {done.skipped ? <T muted size={13}>{done.skipped} déjà {done.skipped > 1 ? 'relancés' : 'relancé'} aujourd’hui : une relance par jour.</T> : null}
              {!done.notified && !shareTo.length && !done.skipped ? <T muted size={14}>Personne à relancer pour l’instant.</T> : null}
              {note ? <T size={13} weight="semibold" color={colors.accent}>{note}</T> : null}
              <Button variant={shareTo.length && !done.marked ? 'secondary' : 'primary'} label="Fermer" onPress={close} />
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 12, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.lineStrong },
  line: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  shareBox: { borderWidth: 1, borderColor: colors.lineStrong },
  preview: { padding: 10, borderRadius: radius.md, backgroundColor: colors.surface2 },
  grow: { flexGrow: 1, flexBasis: 90 },
});
