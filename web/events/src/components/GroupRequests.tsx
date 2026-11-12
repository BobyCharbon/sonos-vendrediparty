import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { formatShort } from '@/lib/format';
import { answerRequest, answerSentence, fetchGroupRequests, type GroupRequest } from '@/lib/groupAnnounce';
import { decideJoinRequest, fetchMyJoinRequests, type MyJoinRequest } from '@/lib/invites';
import { enter } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';
import { Button, ErrorText, Section, T } from './ui';

type Props = {
  /** Relu quand la page se rafraîchit (tirer pour actualiser, retour sur l'onglet). */
  refreshKey?: string | number;
};

/**
 * « À valider » (créateur, admins et organisateurs d'un groupe ; titulaires du droit groups.announce_approve) :
 * - les annonces demandées par un membre (« Prévenir le groupe ») : l'aperçu de l'événement et du message reçu ;
 * - les événements proposés à un groupe qui demande une validation.
 * La première réponse gagne pour tous ; une annonce sans réponse part d'office 48 h après la demande.
 */
export function GroupRequests({ refreshKey }: Props) {
  const [items, setItems] = useState<GroupRequest[] | null>(null);
  // 12.11 : personnes invitées par un invité, sur mes événements sans lien public ; Accepter ici, sans ouvrir la fiche.
  const [guests, setGuests] = useState<MyJoinRequest[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => fetchGroupRequests().then(
    (rows) => { setItems(rows); setError(null); },
    () => setError('Les demandes à valider ne se chargent pas. Réessaie.'),
  ), []);
  // Une base sans cette fonction (ou une panne) ne cache jamais les demandes de groupe : liste vide, en silence.
  const loadGuests = useCallback(() => fetchMyJoinRequests().then(setGuests, () => setGuests([])), []);
  useEffect(() => { void load(); void loadGuests(); }, [load, loadGuests, refreshKey]);

  async function decide(r: MyJoinRequest, accept: boolean) {
    setBusy(`${r.event_id}:${r.id}:${accept}`);
    try {
      await decideJoinRequest(r.event_id, r.id, accept);
      setNotice(accept ? `${r.name} est invité à « ${r.title} » : il voit l’événement.` : `${r.name} ne verra pas « ${r.title} ».`);
      await loadGuests();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La réponse n’a pas été enregistrée. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  async function answer(r: GroupRequest, accept: boolean) {
    setBusy(`${r.id}:${accept}`);
    try {
      const result = await answerRequest(r, accept);
      setNotice(answerSentence(r, accept, result));
      await load();
    } catch {
      setError('La réponse n’a pas été enregistrée. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  const total = (items?.length ?? 0) + guests.length;
  if (!total) return notice || error ? <View style={{ gap: 6 }}>{notice ? <T size={13} weight="semibold" color={colors.mint}>{notice}</T> : null}<ErrorText error={error} /></View> : null;

  return (
    <Section title="À valider" right={<T size={13} weight="bold" color={colors.coral}>{total}</T>}>
      {guests.map((r) => (
        <View key={`${r.event_id}:${r.id}`} style={[st.card, enter('pop')]}
          accessibilityLabel={`${r.name} aimerait venir à ${r.title}, invité par ${r.invited_by ?? 'un invité'}`}>
          <T size={12} weight="bold" color={colors.accent}>INVITÉ À ACCEPTER · {r.title.toUpperCase()}</T>
          <T weight="bold" size={17}>{r.name} aimerait venir</T>
          <T muted size={13}>
            {[`Invité par ${r.invited_by?.trim() || 'un invité'}`, r.link_label ? `lien « ${r.link_label} »` : null,
              r.date_mode === 'poll' ? 'Date à choisir (sondage)' : r.starts_at ? formatShort(r.starts_at) : null].filter(Boolean).join(' · ')}
          </T>
          <T size={13} color={colors.textSoft}>Accepté, {r.name} voit l’événement et sa réponse compte. Refusé, il ne le voit pas.</T>
          <View style={st.row}>
            <Button small label="Accepter" accessibilityLabel={`Accepter ${r.name}`} style={{ flex: 1 }}
              loading={busy === `${r.event_id}:${r.id}:true`} disabled={!!busy} onPress={() => void decide(r, true)} />
            <Button small variant="secondary" label="Refuser" accessibilityLabel={`Refuser ${r.name}`} style={{ flex: 1 }}
              loading={busy === `${r.event_id}:${r.id}:false`} disabled={!!busy} onPress={() => void decide(r, false)} />
          </View>
        </View>
      ))}
      {(items ?? []).map((r) => (
        <View key={r.id} style={[st.card, enter('pop')]} accessibilityLabel={`${r.kind === 'announce' ? 'Annonce à valider' : 'Événement à valider'} : ${r.title}, pour ${r.group}`}>
          <T size={12} weight="bold" color={colors.accent}>
            {r.kind === 'announce' ? `ANNONCE À VALIDER · ${r.group.toUpperCase()}` : `ÉVÉNEMENT À VALIDER · ${r.group.toUpperCase()}`}
          </T>
          <T weight="bold" size={17}>{r.title}</T>
          <T muted size={13}>
            {[r.date_mode === 'poll' ? 'Date à choisir (sondage)' : r.starts_at ? formatShort(r.starts_at) : null, r.location_name, `par ${r.organizer}`]
              .filter(Boolean).join(' · ')}
          </T>
          {r.description ? <T size={13} numberOfLines={3} color={colors.textSoft}>{r.description}</T> : null}
          {r.kind === 'announce' ? (
            <View style={st.preview} accessibilityLabel={`Message que recevront les ${r.members} membres`}>
              <T size={12} muted>Notification envoyée aux {r.members} membres :</T>
              <T size={14} weight="semibold">{r.message_title}</T>
              <T size={13}>{r.message_body}</T>
            </View>
          ) : (
            <T size={13} color={colors.textSoft}>
              {`Accepté, ${r.group} (${r.members} membres) voit l’événement. Refusé, il reste invisible pour le groupe.`}
              {r.announce ? ' L’organisateur veut aussi prévenir le groupe : accepté, le groupe reçoit aussi la notification.' : ''}
            </T>
          )}
          {r.auto_at ? <T size={12} muted>Sans réponse, l’annonce part d’office {formatShort(r.auto_at)}.</T> : null}
          <View style={st.row}>
            <Button small label="Accepter" style={{ flex: 1 }} loading={busy === `${r.id}:true`} disabled={!!busy} onPress={() => void answer(r, true)} />
            <Button small variant="secondary" label="Refuser" style={{ flex: 1 }} loading={busy === `${r.id}:false`} disabled={!!busy} onPress={() => void answer(r, false)} />
          </View>
        </View>
      ))}
      {notice ? <T size={13} weight="semibold" color={colors.mint}>{notice}</T> : null}
      <ErrorText error={error} />
    </Section>
  );
}

const st = StyleSheet.create({
  card: { gap: 6, padding: 14, borderRadius: radius.md, backgroundColor: colors.surface },
  preview: { gap: 2, padding: 10, borderRadius: radius.sm, backgroundColor: colors.fill },
  row: { flexDirection: 'row', gap: 8, marginTop: 4 },
});
