import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { barPledge, errorText, optionsOf, type MyBar } from '@/lib/bar';
import { colors, font, radius } from '@/lib/theme';

import { Button, ErrorText, Section, T } from '../ui';

/** Service au comptoir (bar payant) : on montre l'engagement s'il n'est pas encore accepté pour les conditions en cours. */
export const needsCounterPledge = (bar: MyBar) => {
  const o = optionsOf(bar);
  return bar.eligible && bar.phase !== 'closed' && !o.free_bar && (o.counter_serve || !o.guest_orders) && bar.pledged_current === false;
};

/**
 * « Être servi au comptoir » : l'engagement à rembourser (texte exact de la base), coché une fois pour ces conditions ;
 * le barman peut ensuite servir sans commande dans l'app.
 */
export function PledgeCard({ eventId, bar, onDone }: { eventId: string; bar: MyBar; onDone: (next: MyBar) => void }) {
  const key = `${bar.pledge_version}|${bar.pledge_text}`;
  const [checkedFor, setCheckedFor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const checked = checkedFor === key;

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      onDone(await barPledge(eventId, bar.pledge_text, bar.pledge_version));
    } catch (e) {
      setCheckedFor(null);
      setError(errorText(e, 'L’engagement n’a pas pu être enregistré. Réessaie.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Être servi au comptoir">
      <T size={14} color={colors.textSoft}>Le barman te sert en scannant ton QR. Avant le premier verre, accepte l’engagement :</T>
      <Pressable accessibilityRole="checkbox" accessibilityState={{ checked }} aria-checked={checked}
        onPress={() => setCheckedFor(checked ? null : key)}
        style={({ pressed }) => [st.check, checked && st.checkOn, pressed && { opacity: 0.85 }]}>
        <View style={[st.box, checked && st.boxOn]}>{checked ? <Text style={st.tick}>✓</Text> : null}</View>
        <T size={14} style={{ flex: 1, lineHeight: 20 }}>{bar.pledge_text}</T>
      </Pressable>
      <Button label="J’accepte l’engagement" disabled={!checked} loading={busy} onPress={() => void accept()} />
      <ErrorText error={error} />
    </Section>
  );
}

const st = StyleSheet.create({
  check: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, minHeight: 44, padding: 12, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.lineStrong, backgroundColor: colors.fill },
  checkOn: { borderColor: colors.mint },
  box: { width: 26, height: 26, borderRadius: 7, borderWidth: 2, borderColor: colors.muted, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.mint, borderColor: colors.mint },
  tick: { color: colors.onMint, fontSize: 16, ...font.bold },
});
