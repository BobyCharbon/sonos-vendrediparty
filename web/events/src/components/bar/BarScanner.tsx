import { useCallback, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useMe } from '@/lib/auth';
import { barScan, errorText, fetchMyBar, PHASE_LABEL, type BarScan } from '@/lib/bar';
import { useQuery } from '@/lib/data';
import { enter } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import { parseScanned } from '@/lib/tickets';

import { nativeScanner, ScanControls } from '../TicketScanner';
import { Badge, Button, Empty, ErrorText, Loading, Screen, T } from '../ui';
import { BarHeader } from './BarHeader';
import { BigButton } from './BigButton';
import { ServedPanel } from './ServedPanel';
import { ServePanel, type Served } from './ServePanel';
import { StockPanel } from './StockPanel';

type Refusal = 'unknown' | 'other_event' | 'not_present' | 'closed' | 'invalid';
type Person = Extract<BarScan, { result: 'ok' }>;
type Step =
  | { kind: 'scan' }
  | { kind: 'person'; raw: string; key: number; person: Person }
  | { kind: 'refused'; result: Refusal; name: string | null }
  | { kind: 'served'; raw: string; served: Served };

const REFUSALS: Record<Refusal, { title: (name: string | null) => string; text: string; bg: string; fg: string }> = {
  unknown: { title: () => 'QR inconnu ou remplacé', text: 'Demande à la personne d’ouvrir « Mon bar » sur la page de l’événement.', bg: colors.red, fg: colors.onRed },
  other_event: { title: () => 'QR d’une autre soirée', text: 'Ce QR est celui d’un autre événement.', bg: colors.red, fg: colors.onRed },
  not_present: { title: (n) => `${n?.trim() || 'Cette personne'} n’est pas noté·e présent·e`, text: 'Seuls les présents commandent au bar. Un organisateur peut changer sa réponse.', bg: colors.red, fg: colors.onRed },
  closed: { title: () => 'Le bar est fermé', text: 'Plus rien à servir : ce qui attendait a été annulé.', bg: colors.coral, fg: colors.onCoral },
  invalid: { title: () => 'Ce n’est pas un QR Party', text: 'Vise le QR de « Mon bar », ou tape le code à 6 signes écrit dessous.', bg: colors.red, fg: colors.onRed },
};

/** Même QR lu plusieurs fois par seconde par la caméra : un seul passage pendant 3 s. */
const SAME_QR_MS = 3000;

function buzz(ok: boolean) {
  try { navigator.vibrate?.(ok ? 30 : [60, 80, 60, 80, 60]); } catch { /* Pas de vibreur. */ }
}

function Refused({ result, name, onNext }: { result: Refusal; name: string | null; onNext: () => void }) {
  const r = REFUSALS[result];
  return (
    <View style={{ gap: 14 }}>
      <View accessibilityRole="alert" style={[st.banner, { backgroundColor: r.bg }, enter('pop')]}>
        <Text style={[st.icon, { color: r.fg }]}>✕</Text>
        <View style={{ flex: 1, gap: 2 }}>
          <T size={19} weight="bold" color={r.fg}>{r.title(name)}</T>
          <T size={14} weight="semibold" color={r.fg}>{r.text}</T>
        </View>
      </View>
      <BigButton label="📷 Scanner le suivant" onPress={onNext} />
    </View>
  );
}

/**
 * Scanner au bar (barmans de la soirée, organisateurs) : QR unique de l'invité (caméra de l'app, du navigateur, ou code à
 * 6 signes), la commande en attente, « Servir », « Servi à … ✓ » avec 10 s pour annuler, puis « Scanner le suivant ».
 */
export function BarScanner({ eventId }: { eventId: string }) {
  const me = useMe();
  const { data: bar, error: loadError, loading, reload } = useQuery(() => fetchMyBar(eventId), [eventId]);
  const [step, setStep] = useState<Step>({ kind: 'scan' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const last = useRef<{ text: string; at: number } | null>(null);
  const seq = useRef(0);

  /** fresh : nouveau scan (le choix du barman repart de zéro) ; sinon simple relecture de la même personne. */
  const lookup = useCallback(async (raw: string, fresh: boolean) => {
    const ticket = parseScanned(raw);
    if (!ticket) { buzz(false); setStep({ kind: 'refused', result: 'invalid', name: null }); return; }
    setBusy(true);
    setError(null);
    try {
      const r = await barScan(eventId, ticket);
      buzz(r.result === 'ok');
      if (r.result === 'ok') {
        const key = fresh ? (seq.current += 1) : seq.current;
        setStep({ kind: 'person', raw, key, person: r });
      } else {
        setStep({ kind: 'refused', result: r.result, name: 'name' in r ? r.name : null });
      }
    } catch (e) {
      buzz(false);
      setError(errorText(e, 'La connexion a échoué. Réessaie.'));
    } finally {
      setBusy(false);
    }
  }, [eventId]);

  const onScanned = useCallback((raw: string) => {
    const now = Date.now();
    if (last.current && last.current.text === raw && now - last.current.at < SAME_QR_MS) return;
    last.current = { text: raw, at: now };
    setNotice(null);
    void lookup(raw, true);
  }, [lookup]);

  const next = useCallback(() => {
    // Le QR de la personne servie est souvent encore devant la caméra : on l'ignore encore 3 s.
    if (last.current) last.current = { ...last.current, at: Date.now() };
    setStep({ kind: 'scan' });
    setError(null);
    setNotice(null);
    void reload();
    const native = nativeScanner();
    if (!native) return;
    // App iPhone : la caméra s'ouvre tout de suite (le barman enchaîne sans toucher deux fois).
    native().then((text) => {
      if (!text) return;
      last.current = { text, at: Date.now() };
      void lookup(text, true);
    }, (e: unknown) => setError(errorText(e, 'Caméra indisponible : tape le code à 6 signes.')));
  }, [lookup, reload]);

  if (loading) return <Loading />;
  const header = <BarHeader title="Scanner au bar" eventId={eventId} />;
  if (!bar || !bar.serve) {
    return (
      <Screen edges={[]}>
        {header}
        {loadError && !bar ? <><ErrorText error={loadError} /><Button variant="secondary" label="Réessayer" onPress={() => void reload()} /></>
          : <Empty>{!bar ? 'Pas de bar pour cet événement.' : 'Réservé aux barmans et organisateurs de la soirée.'}</Empty>}
      </Screen>
    );
  }

  return (
    <Screen edges={[]}>
      {header}
      <View style={st.top}>
        <Badge label={`🍹 ${bar.manage ? 'Organisateur' : 'Barman'} · ${me.display_name}`} fg={colors.onCoral} bg={colors.coral} />
        <T muted size={13}>{PHASE_LABEL[bar.phase]}</T>
      </View>
      {notice ? <T size={14} weight="semibold" color={colors.mint}>{notice}</T> : null}
      {step.kind === 'scan' ? (
        <ScanControls paused={busy} onScanned={onScanned} labels={{
          scan: '📷 Scanner un QR', code: 'Code du QR', placeholder: 'Code sous le QR (ex. K7M 2QX)',
          noCamera: 'Pas de caméra ici : demande le code à 6 signes écrit sous le QR de « Mon bar » et tape-le.',
        }} />
      ) : null}
      {step.kind === 'person' ? (
        <ServePanel key={step.key} eventId={eventId} person={step.person} onNext={next}
          onStale={() => void lookup(step.raw, false)}
          onServed={(served) => setStep({ kind: 'served', raw: step.raw, served })} />
      ) : null}
      {step.kind === 'served' ? (
        <ServedPanel eventId={eventId} served={step.served} onNext={next} onUndone={() => {
          setNotice('Service annulé : rien n’est débité, les verres attendent de nouveau.');
          void lookup(step.raw, true);
        }} />
      ) : null}
      {step.kind === 'refused' ? <Refused result={step.result} name={step.name} onNext={next} /> : null}
      {busy && step.kind === 'scan' ? <T muted size={13}>Lecture du QR…</T> : null}
      <ErrorText error={error} />
      {step.kind === 'scan' ? <StockPanel eventId={eventId} /> : null}
    </Screen>
  );
}

const st = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 18, borderRadius: radius.lg },
  icon: { fontSize: 30, ...font.bold },
});
