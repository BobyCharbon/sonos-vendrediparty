import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { barChf, barCreate, errorText, fetchMyBar, PHASE_LABEL, useBarRefresh, type MyBar } from '@/lib/bar';
import { useQuery } from '@/lib/data';
import { barOn } from '@/lib/features';
import { pressTransition } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';

import { Badge, Button, ErrorText, s, T } from '../ui';
import { BarBalance } from './BarBalance';

/** Les deux entrées de la fiche (carte de l'invité, zone organisateur) lisent my_bar ensemble : une seule requête. */
const SHARE_MS = 2000;
const shared = new Map<string, { at: number; promise: Promise<MyBar | null> }>();

function sharedMyBar(eventId: string): Promise<MyBar | null> {
  const hit = shared.get(eventId);
  const now = Date.now();
  if (hit && now - hit.at < SHARE_MS) return hit.promise;
  const promise = fetchMyBar(eventId);
  shared.set(eventId, { at: now, promise });
  promise.catch(() => shared.delete(eventId));
  return promise;
}

/**
 * Bar de la soirée sur la fiche de l'événement (drapeau barOn) :
 * - zone="organizer" (dans la ZONE ORGANISATEUR) : « Créer le bar de la soirée », puis « Gérer le bar » et « Scanner au bar » ;
 * - zone="guest" : la carte du présent avec son solde EN GRAND et « Ouvrir le bar › » ; le barman y trouve « Scanner au bar ».
 */
export function BarEntry({ eventId, zone }: { eventId: string; zone: 'guest' | 'organizer' }) {
  const { data: bar, error, loading, reload } = useQuery(() => sharedMyBar(eventId), [eventId]);
  useBarRefresh(reload, barOn && !!bar && bar.phase !== 'closed');
  const [busy, setBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  if (!barOn || loading) return null;
  const scan = () => router.push(`/event/${eventId}/bar/scan`);

  if (zone === 'organizer') {
    if (error && !bar) return <T muted size={13}>Le bar de la soirée n’a pas pu être lu.</T>;
    if (!bar) {
      return (
        <View style={{ gap: 6 }}>
          <Button label="🍹 Créer le bar de la soirée" loading={busy} onPress={async () => {
            setBusy(true);
            setCreateError(null);
            try {
              await barCreate(eventId);
              shared.delete(eventId);
              router.push(`/event/${eventId}/bar/manage`);
              void reload();
            } catch (e) {
              setCreateError(errorText(e, 'Le bar n’a pas pu être créé. Réessaie.'));
            } finally {
              setBusy(false);
            }
          }} />
          <ErrorText error={createError} />
        </View>
      );
    }
    if (!bar.manage) return null;
    return (
      <>
        <Button label="🍹 Gérer le bar" onPress={() => router.push(`/event/${eventId}/bar/manage`)} />
        <Button label="🍹 Scanner au bar" onPress={scan} />
      </>
    );
  }

  if (!bar) return null;
  const showCard = bar.eligible || bar.balance > 0 || bar.pending_total > 0 || bar.served.length > 0;
  return (
    <>
      {showCard ? (
        <Pressable accessibilityRole="button" accessibilityLabel={`Ouvrir le bar de la soirée. À rembourser : ${barChf(bar.balance)}`}
          onPress={() => router.push(`/event/${eventId}/bar`)}
          style={({ pressed }) => [s.card, pressTransition, pressed && { transform: [{ scale: 0.98 }], opacity: 0.9 }]}>
          <View style={s.rowBetween}>
            <T weight="bold" size={17}>🍹 Bar de la soirée</T>
            <Badge label={PHASE_LABEL[bar.phase]} fg={bar.phase === 'open' ? colors.onMint : colors.textSoft}
              bg={bar.phase === 'open' ? colors.mint : colors.surface2} />
          </View>
          <BarBalance bar={bar} compact />
          <T size={14} weight="bold" color={colors.accent} style={{ alignSelf: 'flex-end' }}>Ouvrir le bar ›</T>
        </Pressable>
      ) : null}
      {bar.serve && !bar.manage ? (
        <View style={st.zone}>
          <T muted size={12} weight="bold">BARMAN</T>
          <Button label="🍹 Scanner au bar" onPress={scan} />
        </View>
      ) : null}
    </>
  );
}

const st = StyleSheet.create({
  zone: { padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, borderStyle: 'dashed', gap: 8 },
});
