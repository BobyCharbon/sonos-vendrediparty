import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { amount, barChf, barConfirmRefund, errorText, round2, stockParts, type BarItem, type BarOverview, type BarPerson } from '@/lib/bar';
import { formatTime, plural } from '@/lib/format';
import { colors, font, radius } from '@/lib/theme';

import { Avatar, Badge, Button, ErrorText, Meter, Section, T } from '../ui';

const PART = { served: colors.lavender, pending: colors.coral, free: colors.mint };

/** Stock virtuel d'un article : servis / réservés (commandés, pas servis) / encore disponibles. */
function StockLine({ item }: { item: BarItem }) {
  const parts = stockParts(item);
  const left = item.available ?? 0;
  const right = item.stock == null ? <T muted size={13}>Illimité</T>
    : left < 0 ? <Badge label={`Surréservé de ${-left}`} fg={colors.onRed} bg={colors.red} />
      : left === 0 ? <Badge label="Épuisé" fg={colors.onRed} bg={colors.red} />
        : <T size={13} weight="bold" color={left <= 2 ? colors.coral : colors.text}>{left} dispo</T>;
  return (
    <View style={{ gap: 5 }}>
      <View style={st.line}>
        <T weight="semibold" size={14} style={{ flex: 1 }} numberOfLines={1}>{item.emoji ? `${item.emoji} ` : ''}{item.name}</T>
        {right}
      </View>
      {parts ? <Meter height={8} parts={[{ fraction: parts.served, color: PART.served }, { fraction: parts.pending, color: PART.pending },
        { fraction: parts.free, color: PART.free }]} /> : null}
      <T muted size={12}>
        {item.stock != null ? `${item.stock} achetés · ` : ''}{item.served} servis · {item.pending} réservés
      </T>
    </View>
  );
}

function status(p: BarPerson): { text: string; color: string } {
  const declared = round2((p.declared ?? []).reduce((sum, d) => sum + d.amount, 0));
  const waiting = p.pending ? ` · ${p.pending} en attente` : '';
  if (declared > 0) return { text: `Dit avoir remboursé ${barChf(declared)}${waiting}`, color: colors.coral };
  if (p.balance > 0) return { text: `À rembourser${waiting}`, color: colors.muted };
  if (p.refunded > 0) return { text: `✓ Remboursé${waiting}`, color: colors.mint };
  return { text: p.pending ? `${p.pending} en attente` : 'Rien à rembourser', color: colors.muted };
}

/** Onglet « Direct » : totaux, stock virtuel, dernières annulations, qui doit combien (toucher = réservations). */
export function LiveTab({ eventId, overview, onOverview }: { eventId: string; overview: BarOverview; onOverview: (o: BarOverview) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const t = overview.totals;
  const due = round2(t.served_chf - t.refunded_chf);
  const people = [...overview.people].sort((a, b) => (b.declared?.length ?? 0) - (a.declared?.length ?? 0) || b.balance - a.balance);

  async function confirm(refund: string, received: boolean) {
    setBusy(refund);
    setError(null);
    try {
      onOverview(await barConfirmRefund(eventId, refund, received));
    } catch (e) {
      setError(errorText(e, 'La réponse n’a pas pu être enregistrée. Réessaie.'));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <View style={st.stats}>
        <View style={st.stat}><Text style={st.big}>{t.served}</Text><T muted size={12} style={st.center}>servis</T></View>
        <View style={st.stat}><Text style={[st.big, { color: colors.coral }]}>{amount(due)}</Text><T muted size={12} style={st.center}>CHF à recevoir</T></View>
        <View style={st.stat}><Text style={[st.big, { color: colors.mint }]}>{amount(t.refunded_chf)}</Text><T muted size={12} style={st.center}>CHF remboursés</T></View>
      </View>
      <Section title="Stock virtuel">
        {overview.items.length === 0 ? <T muted size={14}>Pas encore d’article.</T> : null}
        {overview.items.map((i) => <StockLine key={i.id} item={i} />)}
        <View style={st.legend}>
          {(['served', 'pending', 'free'] as const).map((k) => (
            <View key={k} style={st.line}>
              <View style={[st.dot, { backgroundColor: PART[k] }]} />
              <T muted size={11}>{k === 'served' ? 'servis' : k === 'pending' ? 'réservés' : 'disponibles'}</T>
            </View>
          ))}
        </View>
      </Section>
      {overview.cancellations.length ? (
        <Section title="Dernières annulations">
          {overview.cancellations.map((c, i) => (
            <View key={`${c.at}-${i}`} style={st.line}>
              <T muted size={13} style={st.hour}>{formatTime(c.at)}</T>
              <T size={14} style={{ flex: 1 }}>
                {c.name ?? '?'} · {c.item ?? 'article'} × {c.qty ?? 1}{c.kind === 'cancelled_by_organizer' ? ' (organisateur)' : ''}
              </T>
            </View>
          ))}
        </Section>
      ) : null}
      <Section title="Qui doit combien" right={<T muted size={12}>Toucher = détail</T>}>
        {people.length === 0 ? <T muted size={14}>Personne n’a encore commandé.</T> : null}
        {people.map((p) => {
          const s = status(p);
          return (
            <View key={p.id} style={{ gap: 6 }}>
              <Pressable accessibilityRole="button" accessibilityLabel={`Détail de ${p.name} : ${barChf(p.balance)} à rembourser`}
                onPress={() => router.push(`/event/${eventId}/bar/person/${p.id}`)}
                style={({ pressed }) => [st.person, pressed && { backgroundColor: colors.fill }]}>
                <Avatar id={p.id} name={p.name} photo={p.avatar_url} size={36} profile={false} />
                <View style={{ flex: 1, minWidth: 0 }}>
                  <T weight="semibold" size={15} numberOfLines={1}>{p.name}</T>
                  <T size={12} color={s.color}>{s.text}</T>
                </View>
                <T size={15} weight="bold" color={p.balance > 0 ? colors.text : colors.muted}>{amount(p.balance)}</T>
                <T muted size={16}>›</T>
              </Pressable>
              {(p.declared ?? []).map((d) => (
                <View key={d.id} style={st.refund}>
                  <T size={13} style={{ width: '100%' }}>{p.name} dit avoir remboursé {barChf(d.amount)} : reçu ?</T>
                  <Button small label="Confirmer" accessibilityLabel={`Confirmer le remboursement de ${p.name}`} loading={busy === d.id}
                    onPress={() => void confirm(d.id, true)} />
                  <Button small variant="ghost" label="Pas reçu" accessibilityLabel={`Remboursement de ${p.name} pas reçu`}
                    disabled={busy === d.id} onPress={() => void confirm(d.id, false)} />
                </View>
              ))}
            </View>
          );
        })}
        {overview.people.length ? <T muted size={12}>{plural(overview.people.length, 'personne a', 'personnes ont')} commandé.</T> : null}
      </Section>
      <ErrorText error={error} />
    </>
  );
}

const st = StyleSheet.create({
  stats: { flexDirection: 'row', gap: 8 },
  stat: { flex: 1, alignItems: 'center', gap: 2, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  center: { textAlign: 'center' },
  big: { ...font.display, color: colors.text, fontSize: 24, lineHeight: 28, fontVariant: ['tabular-nums'] },
  line: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  dot: { width: 9, height: 9, borderRadius: 5 },
  hour: { width: 46, fontVariant: ['tabular-nums'] },
  person: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, marginHorizontal: -8, paddingHorizontal: 8, borderRadius: radius.md },
  refund: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, padding: 10, borderRadius: radius.md, backgroundColor: colors.coralDim },
});
