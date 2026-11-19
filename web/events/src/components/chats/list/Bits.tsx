import { useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { chatFont, useNeon, web, type NeonColors } from '../neon';
import { Icon, type IconName } from './Icons';
import { untilLabel, usePause } from '@/components/NotificationPause';
import { enter, pressTransition, transition } from '@/lib/motion';
import type { PauseScope, PauseSpan } from '@/lib/types';

/** Bouton rond en verre (44 px), icône seule avec un vrai libellé. */
export function IconButton({ icon, label, onPress, on, expanded }: { icon: IconName; label: string; onPress: () => void; on?: boolean; expanded?: boolean }) {
  const c = useNeon();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={expanded === undefined ? undefined : { expanded }} onPress={onPress}
      style={({ pressed }) => [st.ibtn, { backgroundColor: on ? 'rgba(255,179,71,0.18)' : c.glass, borderColor: on ? 'rgba(255,179,71,0.5)' : c.glassLine },
        pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
      <Icon name={icon} size={22} color={on ? c.coral : c.t1} stroke={icon === 'more' ? 2.8 : undefined} />
    </Pressable>
  );
}

/** Grand titre Bricolage et ses boutons à droite (lune = pause, « … » = menu). */
export function ListHeader({ title, children, back }: { title: string; children?: ReactNode; back?: { label: string; onPress: () => void } }) {
  const c = useNeon();
  return (
    <View style={{ zIndex: 30 }}>
      {back ? (
        <Pressable accessibilityRole="button" accessibilityLabel={`Retour : ${back.label}`} onPress={back.onPress}
          style={({ pressed }) => [st.back, pressed && { opacity: 0.6 }]}>
          <Icon name="chevl" size={22} color={c.lav} stroke={2.4} />
          <Text style={[chatFont.medium, { color: c.lav, fontSize: 17 }]}>{back.label}</Text>
        </Pressable>
      ) : null}
      <View style={st.top}>
        <Text role="heading" aria-level={1} numberOfLines={1} style={[chatFont.display, st.h1, { color: c.t1 }]}>{title}</Text>
        <View style={st.acts}>{children}</View>
      </View>
    </View>
  );
}

/** Champ de recherche (verre, loupe, « Annuler » quand il est actif). */
export function SearchField({ value, onChange, active, onFocus, onCancel }: {
  value: string; onChange: (v: string) => void; active: boolean; onFocus: () => void; onCancel: () => void;
}) {
  const c = useNeon();
  return (
    <View style={st.searchRow} aria-label="Recherche">
      <View style={[st.search, { backgroundColor: c.glass, borderColor: active ? c.lav : c.glassLine }, transition('border-color', 160)]}>
        <Icon name="search" size={16} color={c.t3} />
        <TextInput value={value} onChangeText={onChange} onFocus={onFocus} placeholder="Personnes, groupes, messages"
          placeholderTextColor={c.t3} accessibilityLabel="Rechercher dans les discussions" autoCorrect={false} autoCapitalize="none"
          enterKeyHint="search" style={[chatFont.text, st.input, { color: c.t1 }, web({ outlineWidth: 0, outlineStyle: 'none', caretColor: c.pink } as Record<string, unknown>)]} />
        {value ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Effacer la recherche" onPress={() => onChange('')} style={st.clear}>
            <View style={[st.clearDot, { backgroundColor: c.t3 }]}><Icon name="x" size={12} color={c.bg} stroke={3} /></View>
          </Pressable>
        ) : null}
      </View>
      {active ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Annuler la recherche" onPress={onCancel} style={[st.cancel, enter('fade')]}>
          <Text style={[chatFont.medium, { color: c.lav, fontSize: 17 }]}>Annuler</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export type Filter = 'all' | 'unread' | 'direct' | 'group' | 'event';
export const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Tout' }, { key: 'unread', label: 'Non lus' }, { key: 'direct', label: 'Personnes' },
  { key: 'group', label: 'Groupes' }, { key: 'event', label: 'Événements' },
];

/** Filtres en puces qui défilent (Tout / Non lus n / Personnes / Groupes / Événements). */
export function FilterChips({ value, onChange, unread }: { value: Filter; onChange: (f: Filter) => void; unread: number }) {
  const c = useNeon();
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} role="tablist" aria-label="Filtrer"
      style={[{ flexGrow: 0 }, web({ maskImage: 'linear-gradient(90deg, #000 86%, transparent)', WebkitMaskImage: 'linear-gradient(90deg, #000 86%, transparent)' })]}
      contentContainerStyle={st.chips}>
      {FILTERS.map((f) => {
        const on = f.key === value;
        return (
          <Pressable key={f.key} role="tab" aria-selected={on} accessibilityLabel={f.key === 'unread' && unread ? `Non lus, ${unread}` : f.label}
            onPress={() => onChange(f.key)}
            style={({ pressed }) => [st.chip, on
              ? [{ borderColor: 'transparent' }, web({ backgroundImage: c.scheme === 'light' ? 'linear-gradient(135deg, #7B6CF6, #6A5AE0)' : `linear-gradient(135deg, ${c.lavHi}, ${c.lav})`,
                boxShadow: '0 6px 18px -8px rgba(185,167,255,.8)' })]
              : { backgroundColor: c.glass, borderColor: c.glassLine },
            transition('background-color, transform', 160), pressed && { transform: [{ scale: 0.95 }] }]}>
            <Text style={[chatFont.semibold, { fontSize: 15, color: on ? c.chipOn : c.t2 }]}>{f.label}</Text>
            {f.key === 'unread' && unread ? (
              <View style={[st.chipN, { backgroundColor: c.pink }]}><Text style={[chatFont.heavy, { fontSize: 12, color: c.onPink }]}>{unread}</Text></View>
            ) : null}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

/** Lignes fines « Demandes » (pastille rose) et « Archivées » (compte gris). */
export function SlimLinks({ requests, archived, onRequests, onArchived }: { requests: number; archived: number; onRequests: () => void; onArchived: () => void }) {
  const c = useNeon();
  if (!requests && !archived) return null;
  const many = requests > 1 ? 's' : '';
  return (
    <View style={st.slim}>
      {requests ? (
        <Slim c={c} icon="inbox" label="Demandes" a11y={`Demandes de message, ${requests} nouvelle${many}`} onPress={onRequests}>
          <View style={[st.chipN, { backgroundColor: c.pink, marginLeft: 'auto' }, web({ boxShadow: `0 0 10px ${c.pink}` })]}>
            <Text style={[chatFont.heavy, { fontSize: 12, color: c.onPink }]}>{requests}</Text>
          </View>
        </Slim>
      ) : null}
      {archived ? (
        <Slim c={c} icon="archive" label="Archivées" a11y={`Archivées, ${archived}`} onPress={onArchived}>
          <Text style={[chatFont.semibold, { marginLeft: 'auto', fontSize: 14, color: c.t3 }]}>{archived}</Text>
        </Slim>
      ) : null}
    </View>
  );
}

function Slim({ c, icon, label, a11y, onPress, children }: { c: NeonColors; icon: IconName; label: string; a11y: string; onPress: () => void; children: ReactNode }) {
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={a11y} onPress={onPress}
      style={({ pressed }) => [st.slimA, { backgroundColor: c.glass, borderColor: c.glassLine }, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
      <Icon name={icon} size={16} color={c.lav} />
      <Text style={[chatFont.semibold, { fontSize: 15, color: c.t1 }]}>{label}</Text>
      {children}
    </Pressable>
  );
}

/** Bouton flottant rose « Nouveau message » ; se replie en rond ✎ quand on fait défiler vers le bas. */
export function Fab({ collapsed, onPress, bottom }: { collapsed: boolean; onPress: () => void; bottom: number }) {
  const c = useNeon();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="Nouveau message" onPress={onPress}
      style={({ pressed }) => [st.fab, { bottom, paddingLeft: collapsed ? 17 : 18, paddingRight: collapsed ? 17 : 22 },
        web({ backgroundImage: `linear-gradient(135deg, ${c.pinkA}, ${c.pink})`,
          boxShadow: '0 0 0 1px rgba(255,255,255,.25) inset, 0 14px 30px -10px rgba(255,79,154,.85), 0 0 40px -8px rgba(255,79,154,.6)' }),
        transition('transform, padding', 260), pressed && { transform: [{ scale: 0.95 }] }]}>
      <Icon name="compose" size={22} color={c.onPink} stroke={2.3} />
      <View style={[{ overflow: 'hidden', maxWidth: collapsed ? 0 : 200, opacity: collapsed ? 0 : 1 }, transition('max-width, opacity', 260)]}>
        <Text numberOfLines={1} style={[chatFont.bold, { fontSize: 17, color: c.onPink, marginLeft: 10 }]}>Nouveau message</Text>
      </View>
    </Pressable>
  );
}

export type MenuItem = { label: string; icon?: IconName; onPress: () => void; danger?: boolean; hint?: string; badge?: number };

/** Menu déroulant sous les boutons de l'en-tête (verre sombre, cibles de 44 px). */
export function Dropdown({ items, title, children, onClose }: { items: MenuItem[]; title?: string; children?: ReactNode; onClose: () => void }) {
  const c = useNeon();
  return (
    <>
      <Pressable accessible={false} focusable={false} onPress={onClose} style={[StyleSheet.absoluteFill, web({ position: 'fixed' as 'absolute', zIndex: 39 })]} />
      <View role="menu" aria-label={title ?? 'Menu'} style={[st.menu, { backgroundColor: c.sheet, borderColor: c.line2 }, web({ boxShadow: c.shadow }), enter('drop')]}>
        {title ? <Text style={[chatFont.label, { color: c.t3, paddingHorizontal: 14, paddingTop: 12, paddingBottom: 4 }]}>{title}</Text> : null}
        {items.map((it) => (
          <Pressable key={it.label} role="menuitem" accessibilityLabel={it.label} onPress={() => { onClose(); it.onPress(); }}
            style={({ pressed }) => [st.item, pressed && { backgroundColor: c.glass }]}>
            {it.icon ? <Icon name={it.icon} size={18} color={it.danger ? c.danger : c.lav} /> : null}
            <Text style={[chatFont.medium, { flex: 1, fontSize: 16, color: it.danger ? c.danger : c.t1 }]}>{it.label}</Text>
            {it.badge ? <View style={[st.chipN, { backgroundColor: c.pink }]}><Text style={[chatFont.heavy, { fontSize: 12, color: c.onPink }]}>{it.badge}</Text></View> : null}
          </Pressable>
        ))}
        {children}
      </View>
    </>
  );
}

const SPANS: { key: PauseSpan; label: string }[] = [
  { key: '30m', label: '30 min' }, { key: '1h', label: '1 h' }, { key: '2h', label: '2 h' }, { key: 'morning', label: 'Jusqu’à 8 h' },
];
const SUBJECT: Record<Exclude<PauseScope, 'all'>, string> = { chats: 'Groupes et messages', event_chats: 'Discussions des événements' };

/** Pause des Discussions (existante : notification_prefs, set_notification_pause) : messages sans son ni vibration. */
export function PausePanel({ pause }: { pause: ReturnType<typeof usePause> }) {
  const c = useNeon();
  return (
    <View style={{ paddingHorizontal: 14, paddingBottom: 12, gap: 10 }}>
      <Text style={[chatFont.text, { color: c.t2, fontSize: 13, lineHeight: 18 }]}>Les messages arrivent quand même, sans son ni vibration.</Text>
      {(['chats', 'event_chats'] as const).map((scope) => {
        const until = pause.until(scope);
        return (
          <View key={scope} style={{ gap: 6 }}>
            <Text style={[chatFont.semibold, { color: until ? c.coral : c.t1, fontSize: 15 }]}>
              {until ? `🔕 ${SUBJECT[scope]} : en pause jusqu’à ${untilLabel(until)}` : SUBJECT[scope]}
            </Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} role="menu" aria-label={`Mettre en sourdine : ${SUBJECT[scope]}`}>
              {until ? <SpanChip c={c} label="Réactiver" strong onPress={() => void pause.set(scope, 'off')} /> : null}
              {SPANS.map((s) => <SpanChip key={s.key} c={c} label={s.label} a11y={`${SUBJECT[scope]} : ${s.label}`} onPress={() => void pause.set(scope, s.key)} />)}
            </View>
          </View>
        );
      })}
      {pause.error ? <Text style={[chatFont.medium, { color: c.danger, fontSize: 14 }]}>{pause.error}</Text> : null}
    </View>
  );
}

function SpanChip({ c, label, a11y, onPress, strong }: { c: NeonColors; label: string; a11y?: string; onPress: () => void; strong?: boolean }) {
  return (
    <Pressable role="menuitem" accessibilityLabel={a11y ?? label} onPress={onPress}
      style={({ pressed }) => [st.span, { backgroundColor: strong ? 'rgba(185,167,255,0.16)' : c.glass, borderColor: strong ? 'rgba(185,167,255,0.35)' : c.glassLine },
        pressed && { transform: [{ scale: 0.95 }] }]}>
      <Text style={[chatFont.semibold, { color: strong ? c.lav : c.t1, fontSize: 14 }]}>{label}</Text>
    </Pressable>
  );
}

/** Lune de l'en-tête : la pause des Discussions, en menu. */
export function PauseButton() {
  const pause = usePause();
  const [open, setOpen] = useState(false);
  const on = pause.chats !== null || pause.eventChats !== null;
  return (
    <View>
      <IconButton icon="moon" on={on} expanded={open} onPress={() => setOpen((v) => !v)}
        label={on ? 'Discussions en pause : modifier' : 'Couper les notifications des Discussions'} />
      {open ? (
        <Dropdown title="Pause des Discussions" items={[]} onClose={() => setOpen(false)}>
          <PausePanel pause={pause} />
        </Dropdown>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  ibtn: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  back: { flexDirection: 'row', alignItems: 'center', gap: 2, height: 44, paddingHorizontal: 8, alignSelf: 'flex-start' },
  top: { paddingHorizontal: 16, paddingTop: 2, flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 },
  h1: { fontSize: 36, lineHeight: 40, letterSpacing: -1, flexShrink: 1 },
  acts: { flexDirection: 'row', gap: 8, paddingBottom: 2 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 14, paddingHorizontal: 16 },
  search: { flex: 1, height: 44, borderRadius: 14, borderWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 12, paddingRight: 4 },
  input: { flex: 1, minWidth: 0, height: 42, fontSize: 17 },
  clear: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  clearDot: { width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  cancel: { height: 44, justifyContent: 'center', paddingHorizontal: 8 },
  chips: { gap: 8, paddingHorizontal: 16, paddingTop: 12, paddingRight: 40 },
  chip: { height: 36, borderRadius: 18, paddingHorizontal: 14, borderWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  chipN: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  slim: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 6 },
  slimA: { flex: 1, height: 44, borderRadius: 14, borderWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12 },
  fab: { position: 'absolute', right: 16, zIndex: 30, height: 56, borderRadius: 28, flexDirection: 'row', alignItems: 'center' },
  menu: { position: 'absolute', top: 52, right: 0, zIndex: 40, width: 290, borderRadius: 18, borderWidth: 1, paddingVertical: 4, overflow: 'hidden' },
  item: { minHeight: 46, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14 },
  span: { height: 36, paddingHorizontal: 12, borderRadius: 18, borderWidth: 1, justifyContent: 'center' },
});
