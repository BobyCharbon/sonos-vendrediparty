import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { duration, enter, transition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { colors, font, radius } from '@/lib/theme';
import type { PauseScope, PauseSpan } from '@/lib/types';
import { ErrorText, T } from './ui';

/** Durées proposées (avis de l'admin du 3 novembre 2026) : la lune n'a pas de 30 min, les discussions oui.
 * Pendant une pause, les notifications arrivent quand même, mais sans son ni vibration. */
const SPANS: Record<PauseScope, PauseSpan[]> = {
  all: ['1h', '2h', 'morning'], chats: ['30m', '1h', '2h', 'morning'], event_chats: ['30m', '1h', '2h', 'morning'],
};
/** Ce que chaque pause rend silencieux (libellés des lignes). */
const SUBJECTS: Record<PauseScope, string> = {
  all: 'Notifications', chats: 'Discussions des groupes', event_chats: 'Discussions des événements',
};
const SPAN_LABELS: Record<Exclude<PauseSpan, 'off'>, string> = {
  '30m': '30 minutes', '1h': '1 heure', '2h': '2 heures', morning: 'Jusqu’à 8 h du matin',
};
const ZURICH = 'Europe/Zurich';

type PauseRow = { muted_until: string | null; chats_muted_until: string | null; event_chats_muted_until: string | null };
const COLUMNS: Record<PauseScope, keyof PauseRow> = { all: 'muted_until', chats: 'chats_muted_until', event_chats: 'event_chats_muted_until' };
const EMPTY: PauseRow = { muted_until: null, chats_muted_until: null, event_chats_muted_until: null };

/** Fin d'une pause encore en cours (instant), sinon null : une date passée ne compte plus. */
export function activeUntil(value: string | null | undefined, now = Date.now()): number | null {
  const at = value ? Date.parse(value) : NaN;
  return Number.isFinite(at) && at > now ? at : null;
}

/** « 14:30 », ou « demain 08:00 » quand la pause finit un autre jour (heure du groupe, Zurich). */
export function untilLabel(at: number, now = Date.now()): string {
  const day = (t: number) => new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, dateStyle: 'short' }).format(t);
  const time = new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, hour: '2-digit', minute: '2-digit' }).format(at);
  return day(at) === day(now) ? time : `demain ${time}`;
}

/** Pauses du compte connecté (notification_prefs), relues à chaque retour sur l'écran ; set() les change. */
export function usePause() {
  const { profile } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, tick] = useState(0);
  const { data, setData } = useQuery(async () => {
    if (!profile) return null;
    const { data: row, error: e } = await supabase.from('notification_prefs')
      .select('muted_until, chats_muted_until, event_chats_muted_until').eq('user_id', profile.id).maybeSingle();
    if (e) throw new Error('La pause n’a pas pu être lue.');
    return { ...EMPTY, ...((row as Partial<PauseRow> | null) ?? {}) };
  }, [profile?.id]);

  const until = (scope: PauseScope) => activeUntil(data?.[COLUMNS[scope]]);
  const all = until('all');
  const chats = until('chats');
  const eventChats = until('event_chats');
  // La pause finit toute seule : l'écran se remet à jour à l'heure dite.
  useEffect(() => {
    const next = Math.min(all ?? Infinity, chats ?? Infinity, eventChats ?? Infinity);
    if (!Number.isFinite(next)) return;
    const id = setTimeout(() => tick((n) => n + 1), Math.min(next - Date.now() + 500, 2 ** 31 - 1));
    return () => clearTimeout(id);
  }, [all, chats, eventChats]);

  async function set(what: PauseScope, span: PauseSpan) {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const { data: row, error: e } = await supabase.rpc('set_notification_pause', { what, span });
      if (e || !row) throw new Error();
      setData({ muted_until: row.muted_until ?? null, chats_muted_until: row.chats_muted_until ?? null,
        event_chats_muted_until: row.event_chats_muted_until ?? null });
      // Party (titre qui passe, jeux) apprend la lune en reliant le compte.
      if (typeof window !== 'undefined' && window.parent !== window) window.parent.postMessage({ type: 'party-events:account' }, location.origin);
    } catch {
      setError('La pause n’a pas été enregistrée. Vérifie ta connexion et réessaie.');
    } finally { setBusy(false); }
  }
  return { all, chats, eventChats, until, busy, error, set, ready: data !== null };
}

type MenuProps = { what: PauseScope; until: number | null; busy: boolean; onPick: (span: PauseSpan) => void };

/** Liste des durées, plus « Réactiver » quand la pause est en cours. */
export function PauseMenu({ what, until, busy, onPick }: MenuProps) {
  return (
    <View style={[styles.menu, enter('drop')]} role="menu" accessibilityLabel={`Mettre en sourdine : ${SUBJECTS[what]}`}>
      {until ? <Item label="Réactiver maintenant" strong disabled={busy} onPress={() => onPick('off')} /> : null}
      {SPANS[what].map((span) => (
        <Item key={span} label={SPAN_LABELS[span as Exclude<PauseSpan, 'off'>]} disabled={busy} onPress={() => onPick(span)} />
      ))}
    </View>
  );
}

function Item({ label, onPress, disabled, strong }: { label: string; onPress: () => void; disabled?: boolean; strong?: boolean }) {
  return (
    <Pressable role="menuitem" accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress}
      style={({ pressed }) => [styles.item, transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }]}>
      <Text style={[styles.itemText, strong && { color: colors.accent, ...font.semibold }]}>{label}</Text>
    </Pressable>
  );
}

/** Lune en haut à droite de la racine des Réglages : toutes les notifications (admin comprises) arrivent sans son. */
export type Pause = ReturnType<typeof usePause>;

export function MoonButton({ pause }: { pause: Pause }) {
  const [open, setOpen] = useState(false);
  const on = pause.all !== null;
  const label = on ? `Notifications en pause jusqu’à ${untilLabel(pause.all!)}` : 'Mettre les notifications en pause';
  return (
    <View style={styles.moonWrap}>
      <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={({ pressed }) => [styles.moon, on && styles.moonOn, { opacity: pressed ? 0.6 : 1 }]}>
        <Text style={[styles.moonGlyph, on && { color: colors.onCoral }]}>{on ? '🌙' : '☾'}</Text>
      </Pressable>
      {open ? (
        <View style={styles.dropdown}>
          <T muted size={12} style={{ paddingHorizontal: 14, paddingTop: 10 }}>
            {on ? label : 'Toutes les notifications arrivent sans son ni vibration'}
          </T>
          <PauseMenu what="all" until={pause.all} busy={pause.busy} onPick={(span) => { setOpen(false); void pause.set('all', span); }} />
        </View>
      ) : null}
      <ErrorText error={pause.error} />
    </View>
  );
}

/** Bandeau sous le titre des Réglages quand la lune est mise. */
export function MoonBanner({ pause }: { pause: Pause }) {
  if (pause.all === null) return null;
  return (
    <View style={styles.banner} role="status">
      <T size={14} style={{ flex: 1 }}>🌙 Notifications en pause jusqu’à {untilLabel(pause.all)} : elles arrivent sans son ni vibration.</T>
      <Pressable accessibilityRole="button" accessibilityLabel="Réactiver les notifications" disabled={pause.busy} onPress={() => pause.set('all', 'off')}>
        <Text style={styles.link}>Réactiver</Text>
      </Pressable>
    </View>
  );
}

/** Pause d'une sorte de discussion (groupes, ou événements : deux boutons distincts) : en haut de la liste des
 * Discussions et dans Réglages › Notifications. Les messages arrivent alors sans son ni vibration. */
export function ChatsPause({ scope = 'chats', compact = false }: { scope?: Exclude<PauseScope, 'all'>; compact?: boolean }) {
  const pause = usePause();
  const [open, setOpen] = useState(false);
  const until = pause.until(scope);
  const status = until ? `🔕 ${SUBJECTS[scope]} en pause jusqu’à ${untilLabel(until)}` : `Mettre en sourdine : ${SUBJECTS[scope]}`;
  return (
    <View style={{ gap: 6 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={status} accessibilityState={{ expanded: open }} onPress={() => setOpen((v) => !v)}
        style={({ pressed }) => [styles.row, compact && styles.rowCompact, pressed && { backgroundColor: colors.fill }]}>
        <Text style={[styles.itemText, { flex: 1 }, until ? { color: colors.coral } : null]}>{status}</Text>
        <Text style={styles.link}>{open ? 'Fermer' : until ? 'Modifier' : 'Pause…'}</Text>
      </Pressable>
      {open ? <PauseMenu what={scope} until={until} busy={pause.busy} onPick={(span) => { setOpen(false); void pause.set(scope, span); }} /> : null}
      <ErrorText error={pause.error} />
    </View>
  );
}

const styles = StyleSheet.create({
  moonWrap: { position: 'absolute', top: 0, right: 0, zIndex: 20, alignItems: 'flex-end' },
  moon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.fill },
  moonOn: { backgroundColor: colors.coral },
  moonGlyph: { fontSize: 22, color: colors.textSoft, lineHeight: 26 },
  dropdown: { marginTop: 8, width: 260, borderRadius: radius.md, backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.lineStrong,
    shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 18, shadowOffset: { width: 0, height: 8 } },
  menu: { paddingVertical: 4 },
  item: { paddingHorizontal: 14, paddingVertical: 12, minHeight: 44, justifyContent: 'center' },
  itemText: { color: colors.text, fontSize: 16, ...font.body },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: radius.md, backgroundColor: colors.coralDim },
  link: { color: colors.accent, fontSize: 15, ...font.semibold },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, minHeight: 44,
    paddingVertical: 8, borderRadius: radius.md },
  rowCompact: { paddingHorizontal: 16 },
});
