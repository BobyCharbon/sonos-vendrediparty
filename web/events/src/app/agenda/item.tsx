import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { goBack, Note } from '@/components/agenda/Bits';
import { Button, Chip, ConfirmButton, ErrorText, Field, Input, Screen, T, Toast, ToggleRow } from '@/components/ui';
import {
  addDays, ALERTS, dayKey, durationText, errorText, hm, minutesOf, nativeAgenda, REPEATS, rpc, shortDay, zdate,
  type DayKey, type Item, type Repeat,
} from '@/lib/agenda';
import { supabase } from '@/lib/supabase';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/** Heures proposées, toutes les 5 minutes. */
const TIMES = Array.from({ length: 288 }, (_, i) => `${String(Math.floor(i / 12)).padStart(2, '0')}:${String((i % 12) * 5).padStart(2, '0')}`);
const toMin = (t: string) => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
const toTime = (m: number) => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

/**
 * Nouveau rendez-vous / modifier (maquette 2E) : titre, jour, de, à ; le reste dans « Plus d'options » (lieu, toute la
 * journée, répéter, alerte, compte comme Occupé). Toujours dit où il va : « Juste pour moi », visible par toi seulement.
 * Le soir (dès 18 h), la durée proposée est de 2 h. Supprimer un rendez-vous qui se répète : celui-ci, les suivants, tous.
 */
export default function AgendaItemScreen() {
  const p = useLocalSearchParams<{ id?: string; occ?: string; day?: string; from?: string }>();
  const editing = typeof p.id === 'string' && /^[0-9a-f-]{36}$/i.test(p.id) ? p.id : null;
  const today = dayKey(new Date());
  const startDay: DayKey = typeof p.day === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(p.day) ? p.day : today;
  const startFrom = typeof p.from === 'string' && /^\d{2}:\d{2}$/.test(p.from) ? p.from : defaultStart(startDay);
  const [title, setTitle] = useState('');
  const [day, setDay] = useState<DayKey>(startDay);
  const [from, setFrom] = useState(startFrom);
  const [to, setTo] = useState(toTime(toMin(startFrom) + defaultLength(startFrom)));
  const [more, setMore] = useState(false);
  const [place, setPlace] = useState('');
  const [notes, setNotes] = useState('');
  const [allDay, setAllDay] = useState(false);
  const [repeat, setRepeat] = useState<Repeat>('none');
  const [alert, setAlert] = useState<number | null>(null);
  const [busy, setBusy] = useState(true);
  const [toPhone, setToPhone] = useState(false);
  const [otherDay, setOtherDay] = useState(false);
  const [item, setItem] = useState<Item | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const native = nativeAgenda();

  useEffect(() => {
    if (!editing) return;
    void supabase.from('agenda_items').select('*').eq('id', editing).maybeSingle().then(({ data }) => {
      const it = data as Item | null;
      if (!it) { setError('Ce rendez-vous n’existe plus.'); return; }
      setItem(it);
      const s = new Date(it.starts_at);
      const e = new Date(it.ends_at);
      setTitle(it.title);
      setDay(dayKey(s));
      setFrom(toTime(minutesOf(s)));
      setTo(toTime(minutesOf(e)));
      setPlace(it.place ?? '');
      setNotes(it.notes ?? '');
      setAllDay(it.all_day);
      setRepeat(it.repeat);
      setAlert(it.alert_minutes);
      setBusy(it.busy);
      if (it.place || it.notes || it.all_day || it.repeat !== 'none' || it.alert_minutes != null || !it.busy) setMore(true);
    });
  }, [editing]);

  function changeFrom(v: string) {
    // La durée choisie suit le début ; tant qu'elle est celle proposée, elle suit la règle (1 h, 2 h le soir).
    const length = toMin(to) - toMin(from);
    const keep = length > 0 && length !== defaultLength(from) ? length : defaultLength(v);
    setFrom(v);
    setTo(toTime(Math.min(toMin(v) + keep, 23 * 60 + 55)));
  }

  function times(): { starts: Date; ends: Date } | string {
    if (allDay) return { starts: zdate(day), ends: zdate(addDays(day, 1)) };
    const a = toMin(from);
    const b = toMin(to);
    // « À » avant « De » : le rendez-vous finit le lendemain (soirée jusqu'à 2 h).
    const ends = b > a ? zdate(day, b) : zdate(addDays(day, 1), b);
    if (b === a) return 'La fin doit être après le début.';
    return { starts: zdate(day, a), ends };
  }

  async function save() {
    if (!title.trim()) { setError('Donne un titre au rendez-vous.'); return; }
    const t = times();
    if (typeof t === 'string') { setError(t); return; }
    setSaving(true);
    setError(null);
    try {
      await rpc('agenda_item_save', {
        item: { title: title.trim(), starts_at: t.starts.toISOString(), ends_at: t.ends.toISOString(), place: place.trim() || null,
          notes: notes.trim() || null, all_day: allDay, repeat, alert_minutes: alert, busy },
        ...(editing ? { id: editing } : {}),
      });
      // « Ajouter aussi à mon iPhone » : la fenêtre d'iOS, déjà remplie (sans autorisation) ; rien ne part au serveur.
      if (toPhone && native) {
        try { await native.addToPhone({ title: title.trim(), start: t.starts.toISOString(), end: t.ends.toISOString(), location: place.trim() || undefined }); }
        catch { /* La personne a fermé la fenêtre d'iOS : le rendez-vous reste dans Party. */ }
      }
      setToast(editing ? 'Rendez-vous enregistré.' : 'Ajouté à ton agenda.');
      setTimeout(() => goBack('/agenda'), 600);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  }

  async function remove(scope: 'all' | 'one' | 'following') {
    if (!editing) return;
    try {
      await rpc('agenda_item_delete', { id: editing, scope, occurrence: scope === 'all' ? null : dayKey(new Date(typeof p.occ === 'string' ? p.occ : item!.starts_at)) });
      goBack('/agenda');
    } catch (e) {
      setError(errorText(e));
    }
  }

  const evening = toMin(from) >= 18 * 60 && !allDay;
  const t = times();
  const partyHref = typeof t === 'string' ? '/event/new'
    : `/event/new?title=${encodeURIComponent(title.trim())}&start=${encodeURIComponent(t.starts.toISOString())}&end=${encodeURIComponent(t.ends.toISOString())}`;
  const chips: { key: DayKey; label: string }[] = [{ key: today, label: 'Aujourd’hui' }, { key: addDays(today, 1), label: 'Demain' }];
  if (!chips.some((c) => c.key === day)) chips.push({ key: day, label: shortDay(day).replace(/ \S+$/, '') });

  return (
    <Screen>
      <View style={st.head}>
        <Pressable accessibilityRole="button" onPress={() => goBack('/agenda')} style={st.headBtn}>
          <Text style={{ color: colors.muted, fontSize: 17, ...font.medium }}>Annuler</Text>
        </Pressable>
        <Text role="heading" aria-level={1} style={st.headTitle} numberOfLines={1}>{editing ? 'Rendez-vous' : 'Nouveau rendez-vous'}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel={editing ? 'Enregistrer le rendez-vous' : 'Ajouter le rendez-vous'} testID="item-save"
          disabled={saving} onPress={() => void save()} style={({ pressed }) => [st.headAdd, pressTransition, pressed && { opacity: 0.85 }]}>
          <Text style={{ color: '#fff', fontSize: 16, ...font.bold }}>{editing ? 'Enregistrer' : 'Ajouter'}</Text>
        </Pressable>
      </View>

      <View style={st.titleBox}>
        <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>TITRE</T>
        <Input accessibilityLabel="Titre du rendez-vous" placeholder="Apéro avec Inès" value={title} onChangeText={setTitle} maxLength={120}
          autoFocus={!editing} style={st.titleInput} />
      </View>

      {item?.booking ? <Note icon="🔗">Rendez-vous pris par ton lien « {item.booking.link_name} ». Le supprimer l’annule pour la personne.</Note> : null}
      {item && item.repeat !== 'none' ? <Note icon="🔁">Les changements valent pour toute la série.</Note> : null}

      <T size={12} weight="bold" color={colors.muted} style={st.label}>JOUR</T>
      <View style={st.wrap}>
        {chips.map((c) => <Chip key={c.key} label={c.label} selected={day === c.key} onPress={() => { setDay(c.key); setOtherDay(false); }} />)}
        <Chip label="Autre jour…" selected={otherDay} onPress={() => setOtherDay(!otherDay)} />
      </View>
      {otherDay ? (
        <View style={enter('drop')}>
          <input aria-label="Jour du rendez-vous" type="date" value={day} onChange={(e) => { if (e.target.value) setDay(e.target.value); }}
            style={{ ...box, width: '100%' }} />
        </View>
      ) : null}

      {!allDay ? (
        <>
          <T size={12} weight="bold" color={colors.muted} style={st.label}>HEURES</T>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <TimeBox label="De" value={from} onChange={changeFrom} />
            <T muted size={18}>→</T>
            <TimeBox label="À" value={to} onChange={setTo} />
          </View>
          {evening && !editing ? <Note>Le soir, la durée proposée est de 2 h.</Note> : null}
          {toMin(to) <= toMin(from) ? <Note icon="🌙">Finit le lendemain à {to}.</Note> : null}
        </>
      ) : <Note icon="📅">Toute la journée, le {shortDay(day)}.</Note>}

      <View style={st.optCard}>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: more }} onPress={() => setMore(!more)} style={st.optHead}>
          <View style={{ flex: 1 }}>
            <T size={16} weight="semibold">Plus d’options</T>
            <T muted size={13}>Lieu, toute la journée, répéter, alerte, occupé</T>
          </View>
          <T muted size={18}>{more ? '⌃' : '⌄'}</T>
        </Pressable>
        {more ? (
          <View style={[{ gap: 12, paddingTop: 4 }, enter('drop')]}>
            <Field label="Lieu" placeholder="Facultatif" value={place} onChangeText={setPlace} maxLength={120} />
            <ToggleRow label="Toute la journée" value={allDay} onChange={setAllDay} />
            <View style={{ gap: 6 }}>
              <T muted size={13} weight="medium">Répéter</T>
              <View style={st.wrap}>{REPEATS.map((r) => <Chip key={r.key} label={r.label} selected={repeat === r.key} onPress={() => setRepeat(r.key)} />)}</View>
            </View>
            <View style={{ gap: 6 }}>
              <T muted size={13} weight="medium">Alerte</T>
              <View style={st.wrap}>{ALERTS.map((a) => <Chip key={String(a.minutes)} label={a.label} selected={alert === a.minutes} onPress={() => setAlert(a.minutes)} />)}</View>
            </View>
            <ToggleRow label="Compte comme Occupé" hint="Pour tes dispos partagées et tes liens (jamais le titre)" value={busy} onChange={setBusy} />
            <Field label="Notes" placeholder="Pour toi seulement" value={notes} onChangeText={setNotes} multiline maxLength={1000} />
          </View>
        ) : null}
        <View style={st.where}>
          <View style={[st.dotMint]} />
          <View style={{ flex: 1 }}>
            <T size={15} weight="semibold">Va dans « Juste pour moi »</T>
            <T muted size={13}>Visible par toi seulement. Rien ne part.</T>
          </View>
        </View>
        {native ? (
          <ToggleRow label="Ajouter aussi à mon iPhone" hint="Ton iPhone va te demander de confirmer" value={toPhone} onChange={setToPhone} />
        ) : null}
      </View>

      <ErrorText error={error} />

      {!editing ? (
        <Pressable accessibilityRole="link" accessibilityLabel="Tu veux inviter du monde ? En faire une soirée Party, avec invités et discussion"
          onPress={() => router.push(partyHref as Href)} style={({ pressed }) => [st.party, pressTransition, pressed && { opacity: 0.85 }]}>
          <Text style={{ fontSize: 26 }}>🎉</Text>
          <View style={{ flex: 1 }}>
            <T size={16} weight="bold">Tu veux inviter du monde ?</T>
            <T size={13} color={colors.textSoft}>En faire une soirée Party, avec invités et discussion.</T>
          </View>
          <T size={20} color={colors.accent}>›</T>
        </Pressable>
      ) : null}

      {editing && item ? (
        item.repeat !== 'none' ? (
          <View style={{ gap: 8 }}>
            <ConfirmButton label="Supprimer seulement celui-ci" confirmLabel="Supprimer" onConfirm={() => remove('one')} />
            <ConfirmButton label="Celui-ci et les suivants" confirmLabel="Supprimer" onConfirm={() => remove('following')} />
            <ConfirmButton label="Toute la série" confirmLabel="Supprimer" onConfirm={() => remove('all')} />
          </View>
        ) : <ConfirmButton label="Supprimer le rendez-vous" confirmLabel="Supprimer" onConfirm={() => remove('all')} />
      ) : null}
      {editing ? <Button variant="ghost" label="Retour à l’agenda" onPress={() => goBack('/agenda')} /> : null}
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
      <T muted size={12} style={{ textAlign: 'center' }}>{typeof t === 'string' ? '' : `${shortDay(day)} · ${allDay ? 'toute la journée' : `${hm(t.starts)} – ${hm(t.ends)} · ${durationText(Math.round((t.ends.getTime() - t.starts.getTime()) / 60000))}`}`}</T>
    </Screen>
  );
}

/** Heure de départ proposée : l'heure ronde qui suit (aujourd'hui), 19:00 un autre jour. */
function defaultStart(day: DayKey): string {
  if (day !== dayKey(new Date())) return '19:00';
  const m = Math.min(22 * 60, Math.ceil((minutesOf(new Date()) + 1) / 30) * 30);
  return toTime(m);
}
/** 1 h, 2 h le soir (dès 18 h). */
function defaultLength(from: string): number {
  return toMin(from) >= 18 * 60 ? 120 : 60;
}

function TimeBox({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const list = TIMES.includes(value) ? TIMES : [...TIMES, value].sort();
  return (
    <View style={st.timeBox}>
      <T size={12} weight="bold" color={colors.muted}>{label.toUpperCase()}</T>
      <select aria-label={label === 'De' ? 'Heure de début' : 'Heure de fin'} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ ...box, padding: 0, background: 'transparent', border: 'none', fontSize: 24, fontWeight: 700, appearance: 'none', width: '100%' }}>
        {list.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
    </View>
  );
}

const box = {
  boxSizing: 'border-box', minHeight: 48, padding: '10px 12px', color: colors.text, backgroundColor: colors.fill, border: '1.5px solid transparent',
  borderRadius: 12, outlineColor: colors.accent, fontFamily: font.body.fontFamily, fontSize: 16, colorScheme: 'dark',
} as const;

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 52 },
  headBtn: { minHeight: 44, justifyContent: 'center', paddingRight: 4 },
  headTitle: { flex: 1, textAlign: 'center', color: colors.text, fontSize: 17, ...font.bold },
  headAdd: { minHeight: 44, paddingHorizontal: 18, borderRadius: radius.pill, backgroundColor: colors.action, justifyContent: 'center',
    shadowColor: colors.accent, shadowOpacity: 0.45, shadowRadius: 12 },
  titleBox: { gap: 4, padding: 12, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.accent, backgroundColor: colors.surface },
  titleInput: { backgroundColor: 'transparent', paddingHorizontal: 0, fontSize: 20, height: 40, borderWidth: 0 },
  label: { letterSpacing: 0.8, marginTop: 4 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  timeBox: { flex: 1, gap: 2, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.lineStrong },
  optCard: { gap: 10, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  optHead: { flexDirection: 'row', alignItems: 'center', minHeight: 44 },
  where: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line },
  dotMint: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.mint },
  party: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, borderRadius: radius.lg, borderWidth: 1, borderColor: 'rgba(255,79,154,0.45)',
    backgroundColor: '#2C1840' },
});
