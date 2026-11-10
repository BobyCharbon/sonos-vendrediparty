import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { barChf, barUndoServe, errorText } from '@/lib/bar';
import { enter } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

import { ErrorText, Meter, T } from '../ui';
import { BigButton } from './BigButton';
import type { Served } from './ServePanel';

/** 10 s à l'écran pour annuler (la base accepte 15 s, réseau compris) ; ensuite seul un organisateur corrige. */
const UNDO_SECONDS = 10;
const TICK_MS = 250;

/** « Servi à Léa ✓ » : ce qui est débité, le solde avant → après, « Annuler · 10 s », puis « Scanner le suivant ». */
export function ServedPanel({ eventId, served, onUndone, onNext }: {
  eventId: string; served: Served; onUndone: () => void; onNext: () => void;
}) {
  const [left, setLeft] = useState(UNDO_SECONDS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Le compte à rebours part à l'affichage, juste après la réponse de la base.
    const end = Date.now() + UNDO_SECONDS * 1000;
    const timer = setInterval(() => {
      const seconds = Math.max(0, Math.ceil((end - Date.now()) / 1000));
      setLeft(seconds);
      if (!seconds) clearInterval(timer);
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [served.serveId]);

  async function undo() {
    setBusy(true);
    setError(null);
    try {
      await barUndoServe(eventId, served.serveId);
      onUndone();
    } catch (e) {
      setError(errorText(e, 'L’annulation n’a pas pu être enregistrée.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={st.wrap}>
      <View accessibilityRole="alert" accessibilityLabel={`Servi à ${served.name}. Débité ${barChf(served.total)}.`} style={[st.done, enter('pop')]}>
        <View style={st.check}><Text style={st.checkMark}>✓</Text></View>
        <Text style={st.title}>Servi à {served.name}</Text>
      </View>
      <View style={st.card}>
        {served.lines.map((l) => (
          <View key={l.label} style={st.kv}>
            <T size={15} style={{ flex: 1 }}>{l.label} × {l.qty}</T>
            <T size={15} weight="semibold">{barChf(l.total)}</T>
          </View>
        ))}
        <View style={[st.kv, st.sum]}>
          <T size={15} weight="bold" style={{ flex: 1 }}>Débité</T>
          <T size={17} weight="bold">{barChf(served.total)}</T>
        </View>
        <View style={st.kv}>
          <T size={13} muted style={{ flex: 1 }}>Solde de {served.name}</T>
          <T size={14} weight="bold">{barChf(served.before)} → {barChf(served.after)}</T>
        </View>
      </View>
      {left > 0 ? (
        <View style={{ gap: 6 }}>
          <BigButton tone="red" label={`Annuler · ${left} s`} accessibilityLabel={`Annuler ce service, encore ${left} secondes`}
            loading={busy} onPress={() => void undo()} />
          <Meter parts={[{ fraction: left / UNDO_SECONDS, color: colors.red }]} height={5} />
        </View>
      ) : (
        <T muted size={13} style={{ textAlign: 'center' }}>Trop tard pour annuler ici : un organisateur peut corriger depuis « Gérer le bar ».</T>
      )}
      <ErrorText error={error} />
      <BigButton tone="mint" label="📷 Scanner le suivant" onPress={onNext} />
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { gap: 14 },
  done: { alignItems: 'center', gap: 10, paddingVertical: 12 },
  check: { width: 88, height: 88, borderRadius: 44, backgroundColor: colors.mint, alignItems: 'center', justifyContent: 'center' },
  checkMark: { color: colors.onMint, fontSize: 48, lineHeight: 52, ...font.bold },
  title: { ...font.display, color: colors.text, fontSize: 30, lineHeight: 34, textAlign: 'center' },
  card: { gap: 8, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  kv: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sum: { paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line },
});
