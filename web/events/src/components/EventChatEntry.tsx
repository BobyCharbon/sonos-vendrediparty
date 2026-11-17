import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ErrorText, T } from './ui';
import { withoutAnnounceTag } from '@/lib/chats';
import { formatClock, formatMessageTime } from '@/lib/format';
import { NATIVE_CHAT_CLOSED, nativeEventChatSettings } from '@/lib/nativeChat';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { Message } from '@/lib/types';

/** Discussion de l'événement vue depuis sa fiche (17.11) : comme une ligne de WhatsApp (dernier message, heure, pastille
 * verte des non-lus) et la cloche du niveau de notifications (Tout / Mentions seulement / Rien, sourdine). La discussion
 * elle-même : écran natif dans l'app iPhone, page /event/<id>/chat ailleurs. */

export type ChatLevel = 'all' | 'mentions' | 'none';
export type EventChatPrefs = { level: ChatLevel; muted_until: string | null; unread: number };

const LEVELS: { key: ChatLevel; label: string; hint: string }[] = [
  { key: 'all', label: 'Tout', hint: 'Chaque message' },
  { key: 'mentions', label: 'Mentions seulement', hint: 'Quand on te cite ou te répond, @toutlemonde, @present, annonce' },
  { key: 'none', label: 'Rien', hint: 'Aucune notification de cette discussion' },
];
const MUTES = [
  { label: '8 h', ms: 8 * 3600_000 },
  { label: '1 semaine', ms: 7 * 86400_000 },
  { label: 'Toujours', ms: null },
];

function readPrefs(data: unknown): EventChatPrefs | null {
  if (!data || typeof data !== 'object' || Array.isArray(data) || !('unread' in data || 'level' in data)) return null;
  const d = data as Partial<EventChatPrefs>;
  const level = d.level === 'all' || d.level === 'none' ? d.level : 'mentions';
  return { level, muted_until: d.muted_until ?? null, unread: Math.max(0, Number(d.unread) || 0) };
}

export function isMuted(p: EventChatPrefs | null): boolean {
  const until = p?.muted_until;
  return !!until && (until === 'infinity' || Date.parse(until) > Date.now());
}

/** Mes réglages et mes non-lus de la discussion (event_chat_prefs_get). Relus à chaque relecture de la fiche (temps réel,
 * signal event:<id>, retour sur l'écran : `refreshKey`) et quand l'écran natif se ferme. Sans réponse : null (ni pastille
 * ni cloche). */
export function useEventChatPrefs(eventId: string, enabled: boolean, refreshKey: unknown) {
  const [prefs, setPrefs] = useState<EventChatPrefs | null>(null);
  const load = useCallback(async () => {
    if (!enabled) return;
    const { data, error } = await supabase.rpc('event_chat_prefs_get', { e: eventId });
    if (!error) setPrefs(readPrefs(data));
  }, [eventId, enabled]);
  useEffect(() => { void load(); }, [load, refreshKey]);
  useEffect(() => {
    if (typeof window === 'undefined' || !enabled) return undefined;
    const onClosed = () => { void load(); };
    window.addEventListener(NATIVE_CHAT_CLOSED, onClosed);
    return () => window.removeEventListener(NATIVE_CHAT_CLOSED, onClosed);
  }, [load, enabled]);
  return { prefs, setPrefs, reload: load };
}

export type EventChat = ReturnType<typeof useEventChatPrefs>;

function UnreadBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <View style={st.badge} accessibilityLabel={`${count} non lu${count > 1 ? 's' : ''}`}>
      <T size={12} weight="bold" color={colors.onMint}>{count > 99 ? '99+' : count}</T>
    </View>
  );
}

/** En haut de la fiche : « 💬 Discussion » et ses non-lus, sans faire défiler. */
export function EventChatButton({ chat, onOpen }: { chat: EventChat; onOpen: () => void }) {
  const unread = chat.prefs?.unread ?? 0;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={unread ? `Discussion, ${unread} non lu${unread > 1 ? 's' : ''}` : 'Discussion'}
      onPress={onOpen} style={({ pressed }) => [st.topButton, pressed && { opacity: 0.75 }]}>
      <T size={14} weight="semibold" color={colors.text}>💬 Discussion</T>
      <UnreadBadge count={unread} />
    </Pressable>
  );
}

function bellLabel(p: EventChatPrefs): { icon: string; text: string } {
  if (isMuted(p)) return { icon: '🔕', text: 'Sourdine' };
  if (p.level === 'none') return { icon: '🔕', text: 'Rien' };
  return p.level === 'all' ? { icon: '🔔', text: 'Tout' } : { icon: '🔔', text: 'Mentions' };
}

function mutedLine(p: EventChatPrefs): string {
  if (p.muted_until === 'infinity' || !p.muted_until) return 'En sourdine, jusqu’à ce que tu la réactives.';
  return `En sourdine jusqu’au ${formatMessageTime(p.muted_until)}.`;
}

/** La carte « Discussion » de la fiche : façon ligne de WhatsApp, la cloche à droite. */
export function EventChatEntry({ eventId, chat, last, authorName, me, onOpen }: {
  eventId: string;
  chat: EventChat;
  last: Message | null;
  authorName: string;
  me: string;
  onOpen: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { prefs, setPrefs } = chat;
  const unread = prefs?.unread ?? 0;
  const nativeSettings = nativeEventChatSettings();

  async function change(rpc: 'event_chat_set_level' | 'event_chat_mute', args: Record<string, unknown>, next: Partial<EventChatPrefs>) {
    if (!prefs) return;
    const before = prefs;
    setError(null);
    setPrefs({ ...prefs, ...next });
    const { data, error: failed } = await supabase.rpc(rpc, { e: eventId, ...args });
    if (failed) {
      setPrefs(before);
      return setError('Le réglage n’a pas pu être enregistré. Réessaie.');
    }
    // La base renvoie ce qu'elle a gardé (niveau, sourdine) : c'est ce qu'on montre.
    if (readPrefs(data)) setPrefs((p) => p && { ...p, ...readPrefs({ ...p, ...(data as object) })!, unread: p.unread });
  }

  const text = last
    ? `${last.announcement && last.pinned ? '📣 ' : ''}${last.user_id === me ? 'Toi' : authorName} : ${withoutAnnounceTag(last.body) || (last.audio_seconds != null ? '🎤 Message vocal' : '📷 Photo')}`
    : 'Aucun message. Lance la discussion !';
  const today = last ? new Date(last.created_at).toDateString() === new Date().toDateString() : false;
  const bell = prefs ? bellLabel(prefs) : null;

  return (
    <View style={st.card}>
      <View style={st.row}>
        <Pressable onPress={onOpen} accessibilityRole="link"
          accessibilityLabel={`Ouvrir la discussion${unread ? `, ${unread} non lu${unread > 1 ? 's' : ''}` : ''}`}
          style={({ pressed }) => [st.main, pressed && { opacity: 0.8 }]}>
          <View style={st.icon}><T size={22}>💬</T></View>
          <View style={{ flex: 1, minWidth: 0, gap: 3 }}>
            <View style={st.line}>
              <T size={16} weight="bold" numberOfLines={1} style={{ flexShrink: 1 }}>Discussion</T>
              {last ? (
                <T size={12} weight={unread ? 'semibold' : 'body'} color={unread ? colors.mint : colors.muted} style={{ marginLeft: 'auto' }}>
                  {today ? formatClock(last.created_at) : formatMessageTime(last.created_at)}
                </T>
              ) : null}
            </View>
            <View style={st.line}>
              <T size={14} color={unread ? colors.text : colors.textSoft} numberOfLines={2} style={{ flex: 1 }}>{text}</T>
              <UnreadBadge count={unread} />
            </View>
          </View>
        </Pressable>
        {bell ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Notifications de la discussion : ${bell.text}`}
            accessibilityState={{ expanded: menu }} aria-expanded={menu} onPress={() => setMenu((m) => !m)}
            style={({ pressed }) => [st.bell, menu && { backgroundColor: colors.fillStrong }, pressed && { opacity: 0.7 }]}>
            <T size={15}>{bell.icon}</T>
            <T size={11} weight="semibold" color={colors.textSoft}>{bell.text}</T>
          </Pressable>
        ) : null}
      </View>

      {menu && prefs ? (
        <View style={st.menu} accessibilityRole="radiogroup" accessibilityLabel="Notifications de la discussion">
          {LEVELS.map((l) => {
            const on = prefs.level === l.key;
            return (
              <Pressable key={l.key} accessibilityRole="radio" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={l.label}
                onPress={() => void change('event_chat_set_level', { level: l.key }, { level: l.key })}
                style={({ pressed }) => [st.option, pressed && { opacity: 0.7 }]}>
                <View style={[st.radio, on && st.radioOn]} />
                <View style={{ flex: 1 }}>
                  <T size={15} weight={on ? 'semibold' : 'body'}>{l.label}</T>
                  <T muted size={12}>{l.hint}</T>
                </View>
              </Pressable>
            );
          })}
          <View style={st.divider} />
          {isMuted(prefs) ? (
            <View style={st.muteRow}>
              <T muted size={13} style={{ flex: 1 }}>{mutedLine(prefs)}</T>
              <Pressable accessibilityRole="button" onPress={() => void change('event_chat_mute', { until: null }, { muted_until: null })}
                style={({ pressed }) => [st.chip, pressed && { opacity: 0.7 }]}>
                <T size={13} weight="semibold" color={colors.accent}>Réactiver</T>
              </Pressable>
            </View>
          ) : (
            <View style={st.muteRow}>
              <T muted size={13}>Sourdine</T>
              {MUTES.map((m) => {
                const until = m.ms == null ? 'infinity' : new Date(Date.now() + m.ms).toISOString();
                return (
                  <Pressable key={m.label} accessibilityRole="button" accessibilityLabel={`Sourdine ${m.label}`}
                    onPress={() => void change('event_chat_mute', { until }, { muted_until: until })}
                    style={({ pressed }) => [st.chip, pressed && { opacity: 0.7 }]}>
                    <T size={13} weight="semibold">{m.label}</T>
                  </Pressable>
                );
              })}
            </View>
          )}
          {nativeSettings ? (
            <Pressable accessibilityRole="button" onPress={() => { setMenu(false); nativeSettings(eventId); }}
              style={({ pressed }) => [st.option, pressed && { opacity: 0.7 }]}>
              <T size={14} weight="semibold" color={colors.accent}>Réglages de la discussion…</T>
            </Pressable>
          ) : null}
          <ErrorText error={error} />
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, padding: 12, gap: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  main: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  icon: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.mintDim, alignItems: 'center', justifyContent: 'center' },
  line: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  badge: { minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 11, backgroundColor: colors.mint, alignItems: 'center', justifyContent: 'center' },
  bell: { minWidth: 56, minHeight: 52, paddingHorizontal: 6, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', gap: 1, backgroundColor: colors.fill },
  menu: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 8, gap: 2 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, paddingVertical: 6 },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.muted },
  radioOn: { borderColor: colors.mint, borderWidth: 6 },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: 6 },
  muteRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, minHeight: 44 },
  chip: { minHeight: 36, paddingHorizontal: 12, borderRadius: radius.pill, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center' },
  topButton: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 40, paddingHorizontal: 14,
    borderRadius: radius.pill, backgroundColor: colors.fill, borderWidth: 1, borderColor: colors.line },
});
