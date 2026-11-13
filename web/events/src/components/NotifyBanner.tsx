import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Button, T } from './ui';
import { enableNotifications, hiddenForNow, isNativeApp, laterUntil, notifyState, shouldShow, type NotifyState } from '@/lib/notifyBanner';
import { colors, radius } from '@/lib/theme';

/**
 * En haut d'un événement (avis c77d117ab172, 13.11) : « Ne rate rien de cet événement » tant que les notifications de
 * CET appareil sont éteintes. Un toucher les active (demande du système) ; bloquées : l'app iPhone ouvre ses réglages,
 * le web dit où les autoriser. « Plus tard » le cache 24 h. Revenir dans l'app (après les Réglages) relit l'état.
 */
export function NotifyBanner() {
  const [state, setState] = useState<NotifyState | null>(null);
  const [hidden, setHidden] = useState(() => hiddenForNow());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    notifyState().then(setState, () => setState(null));
  }, []);

  useEffect(() => {
    refresh();
    if (typeof document === 'undefined') return;
    const back = () => { if (document.visibilityState === 'visible') refresh(); };
    document.addEventListener('visibilitychange', back);
    return () => document.removeEventListener('visibilitychange', back);
  }, [refresh]);

  if (!shouldShow(state, hidden)) return null;
  const native = isNativeApp();
  const blocked = state === 'denied';

  async function enable() {
    setBusy(true);
    setError(null);
    try {
      setState(await enableNotifications());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Les notifications n’ont pas pu être activées.');
      refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={st.card} accessibilityRole="summary" accessibilityLabel="Notifications désactivées">
      <View style={st.row}>
        <View style={st.bell}><T size={22}>🔔</T></View>
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="bold" size={16}>{blocked ? 'Tes notifications sont bloquées' : 'Ne rate rien de cet événement'}</T>
          <T size={13} color={colors.textSoft}>
            {blocked
              ? native ? 'Autorise Party dans les réglages de l’iPhone pour savoir quand l’heure, le lieu ou la date changent.'
                : 'Autorise les notifications pour ce site dans les réglages du navigateur (le cadenas à côté de l’adresse).'
              : 'Active les notifications : un changement d’heure, une date fixée, un rappel… tu le sais tout de suite.'}
          </T>
        </View>
      </View>
      <View style={st.row}>
        {!blocked || native ? (
          <Button label={blocked ? 'Ouvrir les réglages' : 'Activer les notifications'} small loading={busy} disabled={busy}
            onPress={() => void enable()} style={{ flex: 1 }} />
        ) : null}
        <Button label="Plus tard" variant="ghost" small disabled={busy} onPress={() => { laterUntil(); setHidden(true); }} />
      </View>
      {error ? <T size={12} color={colors.redSoft}>{error}</T> : null}
    </View>
  );
}

const st = StyleSheet.create({
  card: { gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.accentDim, borderWidth: 1.5, borderColor: colors.accent },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  bell: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.fillStrong },
});
