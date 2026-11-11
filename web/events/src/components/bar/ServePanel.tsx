import { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import {
  ageWarnings, amount, barChf, barServe, barStaffCancel, errorCode, errorText, itemLabel, newClientKey, round2, serveMax, servePicks,
  serveAmount, type BarScan, type Cart, type ScanLine,
} from '@/lib/bar';
import { formatTime, plural } from '@/lib/format';
import { enter } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

import { Avatar, Button, ErrorText, T } from '../ui';
import { BigButton } from './BigButton';
import { counterMax, CounterPicks } from './CounterPicks';
import { Stepper } from './Stepper';

export type Served = {
  serveId: string; name: string; total: number; before: number; after: number;
  lines: { label: string; qty: number; total: number }[];
  /** Bar offert : ni montant ni solde. */
  free?: boolean;
  /** L'organisateur a retiré aux barmans l'annulation des services. */
  canUndo?: boolean;
};
type Person = Extract<BarScan, { result: 'ok' }>;

/** Prix figés des verres en attente : « 5 CHF », ou « 5–5.50 CHF » si la carte a changé entre deux commandes. */
function pricesLabel(l: ScanLine): string {
  const prices = (l.prices ?? [l.price_chf]).map(Number);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  return lo === hi ? barChf(lo) : `${barChf(lo).replace(/\s*CHF$/, '')}–${barChf(hi)}`;
}

/** Ce que le barman sert sans commande : lignes, nombre et montant (prix de la carte, 0 en bar offert). */
function counterPicks(person: Person, extras: Cart) {
  const lines = (person.menu ?? []).map((i) => ({ item: i, qty: Math.min(extras[i.item] ?? 0, counterMax(i)) })).filter((l) => l.qty > 0);
  return {
    lines, count: lines.reduce((a, l) => a + l.qty, 0),
    total: round2(lines.reduce((a, l) => a + l.qty * Number(l.item.price_chf), 0)),
  };
}

/**
 * Après le scan (barman) : la personne, son engagement, son solde, ce qu'elle a commandé (0…quantité), et — si
 * l'organisateur le permet — ce qu'on lui sert sans commande ; puis « Servir ». Une clé par geste : un double toucher ou
 * une reprise réseau ne sert jamais deux fois.
 */
export function ServePanel({ eventId, person, onServed, onStale, onNext }: {
  eventId: string; person: Person; onServed: (s: Served) => void; onStale: () => void; onNext: () => void;
}) {
  const [picks, setPicks] = useState<Cart>({});
  const [extras, setExtras] = useState<Cart>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gesture = useRef<string | null>(null);
  const who = person.name?.trim() || 'cette personne';
  const free = !!person.free;
  const ordered = servePicks(person.pending, picks);
  const counter = counterPicks(person, extras);
  const count = ordered.count + counter.count;
  const total = round2(ordered.total + counter.total);
  const after = round2(person.balance + total);
  const warnings = ageWarnings(person.pending);
  const counterOn = !!person.counter && (person.menu?.length ?? 0) > 0;
  const needsPledge = counterOn && !free && person.pledged_current === false;

  function pick(set: typeof setPicks, item: string, qty: number) {
    gesture.current = null;   // autre choix : autre geste
    set((p) => ({ ...p, [item]: qty }));
  }

  async function serve() {
    if (!count || busy) return;
    gesture.current ??= newClientKey();
    setBusy(true);
    setError(null);
    const items = new Set([...ordered.lines.map((l) => l.line.item), ...counter.lines.map((l) => l.item.item)]);
    const payload = [...items].map((item) => ({
      item, qty: ordered.lines.find((l) => l.line.item === item)?.qty ?? 0, extra: counter.lines.find((l) => l.item.item === item)?.qty ?? 0,
    }));
    try {
      const r = await barServe(eventId, person.member, payload, gesture.current);
      gesture.current = null;
      const debited = Number(r.total);
      onServed({
        serveId: r.serve_id, name: who, total: debited, before: r.balance_before ?? round2(Number(r.balance) - debited), after: Number(r.balance),
        lines: [...ordered.lines.map((l) => ({ label: itemLabel(l.line), qty: l.qty, total: serveAmount(l.line, l.qty) })),
          ...counter.lines.map((l) => ({ label: `${itemLabel(l.item)} (comptoir)`, qty: l.qty, total: round2(l.qty * Number(l.item.price_chf)) }))],
        free, canUndo: person.rights?.correct !== false,
      });
    } catch (e) {
      const code = errorCode(e);
      setError(errorText(e, 'Le service n’a pas pu être enregistré. Réessaie.'));
      if (code === 'already_served' || code === 'stock' || code === 'unavailable') { gesture.current = null; onStale(); }
    } finally {
      setBusy(false);
    }
  }

  async function cancelOne(line: ScanLine) {
    setBusy(true);
    setError(null);
    try {
      await barStaffCancel(eventId, person.member, line.item, 1);
      onStale();
    } catch (e) {
      setError(errorText(e, 'L’annulation n’a pas pu être enregistrée.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[st.wrap, enter('pop')]}>
      <View style={st.who}>
        <Avatar id={person.member} name={person.name} photo={person.avatar_url} size={56} profile={false} />
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <T weight="bold" size={20} numberOfLines={2}>{person.name}</T>
          {free ? <T size={13} weight="semibold" color={colors.mint}>Bar offert : rien à payer</T> : (
            <T size={13} weight="semibold" color={person.pledged_at ? colors.mint : colors.coral}>
              {person.pledged_at ? `✓ Engagement accepté à ${formatTime(person.pledged_at)}` : 'Pas encore d’engagement'}
            </T>
          )}
        </View>
        {free ? null : (
          <View style={{ alignItems: 'flex-end' }}>
            <T muted size={11}>Solde</T>
            <Text style={st.balance}>{amount(person.balance)}</Text>
          </View>
        )}
      </View>

      {person.pending.length ? (
        <>
          <T size={14} color={colors.textSoft}>A commandé (choisis ce que tu sers) :</T>
          {person.pending.map((l) => {
            const qty = Math.min(picks[l.item] ?? 0, serveMax(l));
            return (
              <View key={l.item} style={{ gap: 4 }}>
                <View style={[st.pick, qty > 0 && st.pickOn]}>
                  <View style={st.tile}><Text style={{ fontSize: 20 }}>{l.emoji || '🍹'}</Text></View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <T weight="semibold" size={15} numberOfLines={2}>{l.name}</T>
                    <T muted size={12}>{plural(l.qty, 'commandé')}{l.stock != null ? ` · stock ${l.stock}` : ''}{free ? '' : ` · ${pricesLabel(l)}`}</T>
                  </View>
                  <Stepper label={l.name} value={qty} max={serveMax(l)} tone="mint" hideZero disabled={busy} onChange={(n) => pick(setPicks, l.item, n)} />
                </View>
                {person.rights?.correct ? (
                  <Button small variant="ghost" label="Annuler 1 en attente" accessibilityLabel={`Annuler 1 ${l.name} en attente`}
                    disabled={busy} onPress={() => void cancelOne(l)} />
                ) : null}
              </View>
            );
          })}
          {warnings.map((w) => <T key={w} size={13} weight="semibold" color={colors.coral} style={st.warn}>⚠︎ {w}</T>)}
        </>
      ) : counterOn ? null : (
        <T size={15} color={colors.coralSoft}>Rien en attente pour {who} : il ou elle commande d’abord dans « Mon bar ».</T>
      )}

      {counterOn ? (
        <>
          <T size={14} color={colors.textSoft}>Servir sans commande :</T>
          {needsPledge ? (
            <T size={13} weight="semibold" color={colors.coral} style={st.warn}>
              {who} n’a pas encore accepté l’engagement à rembourser : il ou elle le coche dans « Mon bar », puis tu sers.
            </T>
          ) : (
            <CounterPicks menu={person.menu ?? []} picks={extras} free={free} disabled={busy} onPick={(item, n) => pick(setExtras, item, n)} />
          )}
        </>
      ) : null}

      {person.pending.length || counterOn ? (
        <>
          <BigButton label={count ? (free ? `Servir ${plural(count, 'article')}` : `Servir ${plural(count, 'article')} · ${barChf(total)}`) : 'Choisis ce que tu sers'}
            disabled={!count} loading={busy} onPress={() => void serve()} />
          {count && !free ? <T muted size={13} style={{ textAlign: 'center' }}>Son solde passera de {amount(person.balance)} à {barChf(after)}.</T> : null}
        </>
      ) : null}
      <ErrorText error={error} />
      <Button variant="secondary" label="📷 Scanner le suivant" onPress={onNext} />
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { gap: 12 },
  who: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  balance: { ...font.display, color: colors.text, fontSize: 24, lineHeight: 28, fontVariant: ['tabular-nums'] },
  pick: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.line, backgroundColor: colors.surface },
  pickOn: { borderColor: colors.mint, backgroundColor: colors.mintDim },
  tile: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  warn: { padding: 10, borderRadius: radius.sm, backgroundColor: colors.coralDim },
});
