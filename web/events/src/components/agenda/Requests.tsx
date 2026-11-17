import { router, type Href } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ReportSheet } from '@/components/ReportSheet';
import { Button, ErrorText, T } from '@/components/ui';
import { agoText, dateDots, dayAbbr, dayKey, dayOfMonth, durationText, errorText, hoursLeft, longDay, rpc, shortDay, spanText, type Booking } from '@/lib/agenda';
import { enter, pressTransition } from '@/lib/motion';
import type { ReportReason } from '@/lib/moderation';
import { colors, font, radius } from '@/lib/theme';

/**
 * Demandes de rendez-vous reçues par un lien de dispo (maquettes 6E et 6c) : seuls les champs remplis, e-mail et téléphone
 * « non vérifié », « Écrit par la personne, pas par Party. », délai restant en mots. Accepter (le rendez-vous entre dans
 * « Juste pour moi »), Refuser (tout est effacé, le créneau se libère), Signaler, Bloquer l'expéditeur.
 */

const STATUS: Record<Booking['status'], { label: string; fg: string; bg: string }> = {
  pending: { label: '⏳ En attente', fg: colors.coral, bg: 'rgba(255,179,71,0.14)' },
  to_confirm: { label: '⏳ À confirmer', fg: colors.coral, bg: 'rgba(255,179,71,0.14)' },
  accepted: { label: '✓ Accepté · dans ton agenda', fg: colors.mint, bg: 'rgba(91,227,166,0.14)' },
  refused: { label: 'Refusé · effacé', fg: colors.muted, bg: colors.fill },
  expired: { label: 'Sans réponse en 48 h · effacé', fg: colors.muted, bg: colors.fill },
  cancelled: { label: 'Annulé', fg: colors.redSoft, bg: colors.redDim },
};

export function whoOf(b: Booking): string {
  return [b.first_name, b.last_name].filter(Boolean).join(' ') || 'La personne';
}

export function bookingSpan(b: Booking): string {
  const s = new Date(b.starts_at);
  const e = new Date(b.ends_at);
  return `${shortDay(dayKey(s))} · ${spanText(s, e)}`;
}

/** Les quatre gestes d'une demande en attente ; `full` : aussi « Bloquer l'expéditeur » (fiche de la demande). */
export function RequestActions({ b, full, onDone }: { b: Booking; full?: boolean; onDone: (what: string) => unknown }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState(false);
  const [blockAsk, setBlockAsk] = useState(false);
  async function run(what: string, fn: () => Promise<unknown>) {
    setBusy(what);
    setError(null);
    try { await fn(); await onDone(what); } catch (e) { setError(errorText(e)); } finally { setBusy(null); }
  }
  const name = b.first_name || 'la personne';
  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button label="✓ Accepter" accessibilityLabel={`Accepter la demande de ${name}`} style={{ flex: 1 }} loading={busy === 'accept'}
          onPress={() => void run('accept', () => rpc('agenda_booking_decide', { id: b.id, accept: true }))} />
        <Button label="✕ Refuser" accessibilityLabel={`Refuser la demande de ${name}`} variant="secondary" style={{ flex: 1 }} loading={busy === 'refuse'}
          onPress={() => void run('refuse', () => rpc('agenda_booking_decide', { id: b.id, accept: false }))} />
      </View>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button small variant="danger" label="⚑ Signaler" accessibilityLabel={`Signaler la demande de ${name}`} style={{ flex: 1 }} onPress={() => setReport(true)} />
        {full ? <Button small variant="danger" label="⊘ Bloquer l’expéditeur" style={{ flex: 1.4 }} onPress={() => setBlockAsk(true)} /> : null}
      </View>
      {blockAsk ? (
        <View style={[st.ask, enter('fade')]}>
          <T size={14} weight="semibold">Bloquer l’expéditeur ? Ses demandes (même adresse e-mail ou même numéro) ne t’arriveront plus. Celle-ci est refusée.</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={() => setBlockAsk(false)} />
            <Button small variant="dangerSolid" label="Bloquer" style={{ flex: 1 }} loading={busy === 'block'}
              onPress={() => void run('block', () => rpc('agenda_booking_block', { id: b.id }))} />
          </View>
        </View>
      ) : null}
      <ErrorText error={error} />
      <ReportSheet target={report ? { kind: 'booking_request', id: b.id, label: 'cette demande' } : null}
        send={async (reason: ReportReason, comment: string) => { await rpc('agenda_booking_report', { id: b.id, reason, comment: comment.trim() || null }); }}
        onClose={(sent) => { setReport(false); if (sent) void onDone('report'); }} />
    </View>
  );
}

/** Carte d'une demande dans la liste (6E) ; toucher ouvre sa fiche. */
export function RequestCard({ b, onDone, index = 0 }: { b: Booking; onDone: (what: string) => unknown; index?: number }) {
  const s = STATUS[b.status];
  return (
    <View style={[st.card, b.status === 'pending' && st.cardPending, enter('rise', index)]} testID={`request-${b.id}`}>
      <Pressable accessibilityRole="link" accessibilityLabel={`Demande de ${whoOf(b)}, ${longDay(dayKey(new Date(b.starts_at)))}, ${spanText(new Date(b.starts_at), new Date(b.ends_at))}`}
        onPress={() => router.push(`/agenda/requests/${b.id}` as Href)} style={({ pressed }) => [{ gap: 6 }, pressTransition, pressed && { opacity: 0.85 }]}>
        <T size={17} weight="bold">{bookingSpan(b)}</T>
        {b.first_name ? <T muted size={13}>« {whoOf(b)} » · nom écrit par la personne</T> : null}
        {b.message ? <T size={15} numberOfLines={3}>« {b.message} »</T> : null}
        <View style={[st.tag, { backgroundColor: s.bg }]}>
          <Text style={{ color: s.fg, fontSize: 13, ...font.bold }}>{s.label}{b.status === 'pending' ? ` · ${hoursLeft(b.expires_at)} pour répondre` : ''}</Text>
        </View>
      </Pressable>
      {b.status === 'pending' ? <RequestActions b={b} onDone={onDone} /> : null}
    </View>
  );
}

/** Fiche d'une demande (6c). */
export function RequestDetail({ b, onDone }: { b: Booking; onDone: (what: string) => unknown }) {
  const s = new Date(b.starts_at);
  const e = new Date(b.ends_at);
  const k = dayKey(s);
  const st2 = STATUS[b.status];
  const rows: { label: string; value: string | null; unverified?: boolean }[] = [
    { label: 'Prénom', value: b.first_name }, { label: 'Nom', value: b.last_name },
    { label: 'E-mail', value: b.email, unverified: true }, { label: 'Téléphone', value: b.phone, unverified: true },
  ];
  const [cancelAsk, setCancelAsk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <View style={{ gap: 12 }}>
      <View style={[st.detail, enter('pop')]} testID="request-detail">
        <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
          <View style={st.tile}>
            <T size={11} weight="bold" color={colors.accentSoft}>{dayAbbr(k)}.</T>
            <T size={22} weight="bold">{dayOfMonth(k)}</T>
          </View>
          <View style={{ flex: 1 }}>
            <T size={20} weight="bold">{spanText(s, e)}</T>
            <T muted size={14}>{longDay(k)} · {durationText(Math.round((e.getTime() - s.getTime()) / 60000))}</T>
          </View>
        </View>
        <View style={[st.tag, { backgroundColor: st2.bg }]}>
          <Text style={{ color: st2.fg, fontSize: 13, ...font.bold }}>{st2.label}{b.status === 'pending' ? ` · ${hoursLeft(b.expires_at)} pour répondre` : ''}</Text>
        </View>
        {rows.filter((r) => r.value).map((r) => (
          <View key={r.label} style={st.field}>
            <T muted size={14} style={{ width: 86 }}>{r.label}</T>
            <View style={{ flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              <T size={15} weight="semibold">{r.value}</T>
              {r.unverified ? <View style={st.unverified}><Text style={{ color: colors.coral, fontSize: 12, ...font.semibold }}>non vérifié</Text></View> : null}
            </View>
          </View>
        ))}
        {b.message ? (
          <View style={{ gap: 4 }}>
            {b.message_label && b.message_label !== 'Message' ? <T muted size={13}>{b.message_label}</T> : null}
            <T size={15}>« {b.message} »</T>
          </View>
        ) : null}
        {b.status === 'pending' && (b.first_name || b.message) ? (
          <T muted size={12}>Écrit par la personne, pas par Party. Le créneau reste réservé pour elle jusqu’à ta réponse.</T>
        ) : null}
        {b.status === 'pending' ? <RequestActions b={b} full onDone={onDone} /> : null}
        {b.status === 'accepted' ? (
          cancelAsk ? (
            <View style={[st.ask, enter('fade')]}>
              <T size={14} weight="semibold">Annuler ce rendez-vous ? La personne le verra sur sa page de suivi.</T>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button small variant="secondary" label="Garder" style={{ flex: 1 }} onPress={() => setCancelAsk(false)} />
                <Button small variant="dangerSolid" label="Annuler le rendez-vous" style={{ flex: 1.4 }}
                  onPress={async () => { try { await rpc('agenda_booking_owner_cancel', { id: b.id }); await onDone('cancel'); } catch (x) { setError(errorText(x)); } }} />
              </View>
            </View>
          ) : <Button small variant="danger" label="Annuler le rendez-vous" onPress={() => setCancelAsk(true)} />
        ) : null}
        <ErrorText error={error} />
      </View>
      {b.status === 'pending' ? (
        <T size={13} color={colors.textSoft}><Text style={{ ...font.bold }}>Accepter</Text> : « Rendez-vous · {b.first_name ?? ''}{b.last_name ? ` ${b.last_name.charAt(0)}.` : ''} » entre dans ton agenda Party. <Text style={{ ...font.bold }}>Refuser</Text> : le créneau se libère, tout est effacé.</T>
      ) : null}
      <T muted size={12}>Reçue {agoText(b.created_at)} par ton lien « {b.link_name} »{b.decided_at ? ` · décidée le ${dateDots(b.decided_at)}` : ''}. Jamais d’appel ni de SMS de Party vers ce numéro.</T>
    </View>
  );
}

const st = StyleSheet.create({
  card: { gap: 10, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  cardPending: { borderColor: 'rgba(255,79,154,0.45)' },
  tag: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  ask: { gap: 8, padding: 12, borderRadius: radius.md, backgroundColor: colors.redDim },
  detail: { gap: 12, padding: 16, borderRadius: radius.lg, borderWidth: 1.5, borderColor: 'rgba(255,79,154,0.5)', backgroundColor: colors.surface },
  tile: { width: 56, height: 60, borderRadius: 14, backgroundColor: colors.accentDim, alignItems: 'center', justifyContent: 'center' },
  field: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.line },
  unverified: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 6, borderWidth: 1, borderColor: 'rgba(255,179,71,0.6)' },
});
