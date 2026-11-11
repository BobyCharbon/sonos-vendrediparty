import { useEffect, useRef, useState } from 'react';
import { Modal, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetSignal, useSheetTop } from './SheetGesture';
import { Button, T } from './ui';
import { enableWebPush } from '@/lib/push';
import { currentSituation, isEventsScreen, partyTab, rememberAsked, shouldInvite } from '@/lib/pushInvite';
import { colors, radius } from '@/lib/theme';

const SHOW_DELAY_MS = 1500;  // l'écran s'affiche d'abord : la fenêtre ne surgit pas pendant le chargement

/** Le module est-il affiché sur l'onglet Événements de Party (et pas sur Réglages, qui partage le même cadre) ? */
function useOnEventsTab(): boolean {
  const [tab, setTab] = useState<string | null>(() => (typeof window === 'undefined' ? null : partyTab()));
  useEffect(() => {
    if (typeof window === 'undefined' || window.parent === window) return;
    let body: HTMLElement | null = null;
    try { body = window.parent.document.body; } catch { return; }
    const watch = new MutationObserver(() => setTab(partyTab()));
    watch.observe(body, { attributes: true, attributeFilter: ['data-tab'] });
    return () => watch.disconnect();
  }, []);
  return tab === 'events';
}

/**
 * App web installée (Safari iPhone, Android) : propose d'activer les notifications en arrivant dans les Événements
 * (retour de l'admin du 11.11.2026). Un toucher sur « Activer » ouvre la demande du système (iPhone : seulement sur
 * un geste). « Plus tard » : redemandé dans une semaine, 3 fois au plus. Autorisées ou refusées : plus jamais.
 */
export function PushInvite({ path }: { path: string }) {
  const onEventsTab = useOnEventsTab();
  const [open, setOpen] = useState(false);
  const shown = useRef(false);
  const eligible = onEventsTab && isEventsScreen(path);

  useEffect(() => {
    if (!eligible || shown.current || !shouldInvite(currentSituation())) return;
    const timer = setTimeout(() => {
      if (shown.current || !shouldInvite(currentSituation())) return;
      shown.current = true;
      setOpen(true);
    }, SHOW_DELAY_MS);
    return () => clearTimeout(timer);
  }, [eligible]);

  return <PushInviteSheet visible={open} onClose={() => setOpen(false)} />;
}

function PushInviteSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const later = () => {
    if (!done) rememberAsked();
    onClose();
  };
  useSheetDrag(visible, later, card, overlay);
  useSheetSignal(visible);

  async function activate() {
    setBusy(true);
    setError(null);
    try {
      await enableWebPush();  // la demande du système part tout de suite, dans le geste
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Les notifications n’ont pas pu être activées.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={later}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={later} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Activer les notifications">
          <SheetTop onClose={later} />
          <View style={st.bell}><T size={30}>🔔</T></View>
          <T weight="bold" size={22} style={st.center}>{done ? 'C’est activé !' : 'Ne rate aucune soirée'}</T>
          {done ? (
            <>
              <T size={15} color={colors.textSoft} style={st.center}>
                Tu seras prévenu des invitations et des changements. Tu choisis quoi recevoir dans Réglages › Notifications.
              </T>
              <Button label="Terminé" onPress={onClose} />
            </>
          ) : (
            <>
              <T size={15} color={colors.textSoft} style={st.center}>
                Active les notifications pour savoir quand on t’invite, quand une date est fixée ou quand un événement change.
              </T>
              <T muted size={13} style={st.center}>Tu choisis ensuite quoi recevoir dans Réglages › Notifications.</T>
              {error ? <T size={13} weight="semibold" color={colors.coralSoft} style={st.center}>{error}</T> : null}
              <View style={{ gap: 8 }}>
                <Button label={busy ? 'Activation…' : 'Activer les notifications'} loading={busy} onPress={() => void activate()} />
                <Button label="Plus tard" variant="secondary" onPress={later} />
              </View>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  bell: { alignSelf: 'center', width: 60, height: 60, borderRadius: 30, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.fill },
  center: { textAlign: 'center' },
});
