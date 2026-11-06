import { useEffect, useRef, useState } from 'react';
import { Image, Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { Avatar, Button, ErrorText, Input, Segmented, T, Toast } from './ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import {
  copyText, createInvite, inviteLinkUrl, inviteMessage, invitePeople, openMessages, openWhatsApp, ruleSentence, shareInvite,
  type GuestList,
} from '@/lib/invites';
import { pressTransition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import { qrDataUri } from '@/lib/tickets';
import type { EventRow } from '@/lib/types';

type Ev = Pick<EventRow, 'id' | 'title' | 'starts_at' | 'ends_at' | 'all_day'>;
type Mode = 'one' | 'several';
type Until = 'event' | '3d' | '7d';
type Person = { id: string; display_name: string; avatar_url: string | null };
type Group = { id: string; name: string; created_by: string | null; system_key: string | null; member_group_members: { user_id: string }[] };

const DEFAULT_PLACES = 10;
const MAX_PLACES = 50;
const RESULTS_SHOWN = 12;
const DAY = 86_400_000;

function untilDate(until: Until, ev: Ev): string | null {
  if (until === 'event') return null;  // la base choisit : lendemain de l'événement
  return new Date(Date.now() + (until === '3d' ? 3 : 7) * DAY).toISOString();
}

/**
 * Feuille « Inviter » (bêta invites_v2, maquette A) : en haut le lien prêt à partager (feuille de partage du téléphone,
 * WhatsApp, Messages, QR), pour une personne ou pour plusieurs avec places et date limite ; dessous, ajouter des gens de
 * Party (même hors du groupe) ou un groupe, en puces ; en bas, la règle en une phrase. Personne n'entre dans un groupe.
 * Toujours ouverte sur un événement publié : le lien est toujours disponible (jamais « après la publication »).
 * headline : « C'est en ligne : envoie le lien à tes invités » juste après la publication (assistant IA) ;
 * initialPeople : les personnes citées à l'IA, déjà cochées (jamais invitées sans son « Inviter »).
 */
export function InviteSheet({ visible, event, me, list, onClose, onInvited, headline, initialPeople = [] }: {
  visible: boolean; event: Ev; me: { id: string; display_name: string }; list: GuestList; onClose: () => void; onInvited: () => void;
  headline?: string; initialPeople?: string[];
}) {
  const { can } = useAuth();
  const [mode, setMode] = useState<Mode>('several');
  const [places, setPlaces] = useState(DEFAULT_PLACES);
  const [label, setLabel] = useState('');
  const [until, setUntil] = useState<Until>('event');
  const [link, setLink] = useState<string | null>(null);
  const [qr, setQr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [people, setPeople] = useState<Person[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);

  const { data: directory } = useQuery(async () => {
    if (!visible) return null;
    const [p, g] = await Promise.all([
      supabase.from('profiles').select('id, display_name, avatar_url').eq('status', 'active').order('display_name'),
      supabase.from('member_groups').select('id, name, created_by, system_key, member_group_members(user_id)').order('name'),
    ]);
    return { people: (p.data ?? []) as Person[], groups: (g.data ?? []) as Group[] };
  }, [visible]);

  // Pré-sélection (une seule fois, dès que l'annuaire est lu) : les personnes citées, pas encore invitées.
  const preselected = useRef(false);
  useEffect(() => {
    if (preselected.current || !directory || !initialPeople.length) return;
    preselected.current = true;
    const already = new Set(list.people.map((p) => p.id));
    setPeople(directory.people.filter((p) => initialPeople.includes(p.id) && p.id !== me.id && !already.has(p.id)));
  }, [directory, initialPeople, list.people, me.id]);

  const host = me.display_name.split(' ')[0] || 'Moi';
  const when = event.starts_at ? formatShort(event.starts_at).toLowerCase() : null;
  const message = (url: string) => inviteMessage({ name: mode === 'one' ? label : null, host, title: event.title, when, url });
  const reset = () => setLink(null);  // un réglage change : le prochain envoi crée un nouveau lien

  /** Le lien se crée au premier envoi, avec les réglages choisis (jamais de bouton « Créer un lien »). */
  async function ensureLink(): Promise<string | null> {
    if (link) return link;
    setBusy(true);
    setError(null);
    try {
      const made = await createInvite(event.id, mode === 'one' ? 1 : places, untilDate(until, event), mode === 'one' ? label.trim() || null : null);
      const url = inviteLinkUrl(made.token);
      setLink(url);
      onInvited();
      return url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function send(how: 'share' | 'whatsapp' | 'sms' | 'copy' | 'qr') {
    const url = await ensureLink();
    if (!url) return;
    const text = message(url);
    if (how === 'whatsapp') openWhatsApp(text);
    else if (how === 'sms') openMessages(text);
    else if (how === 'qr') setQr(true);
    else if (how === 'copy') setNote((await copyText(url)) ? 'Lien copié' : 'Copie impossible : touche le lien pour le sélectionner');
    else {
      const done = await shareInvite(text, url, event.title);
      if (done === 'copied') setNote('Message copié : colle-le où tu veux');
    }
  }

  // Ajouter des gens de Party : déjà invités signalés, membres du groupe Vendredi Party aussi.
  const invited = new Set(list.people.map((p) => p.id));
  const inVip = new Set(list.people.filter((p) => p.source === 'vip').map((p) => p.id));
  const q = search.trim().toLowerCase();
  const choosable = (directory?.groups ?? []).filter((g) => !g.system_key && !list.groups.some((x) => x.id === g.id)
    && (can('events.manage_all') || g.member_group_members.some((m) => m.user_id === me.id)));  // ses groupes seulement (06.11)
  const foundGroups = choosable.filter((g) => !groups.some((x) => x.id === g.id) && (!q || g.name.toLowerCase().includes(q))).slice(0, q ? RESULTS_SHOWN : 4);
  const matches = q ? (directory?.people ?? []).filter((p) => p.id !== me.id && p.display_name.toLowerCase().includes(q)) : [];
  const foundPeople = matches.filter((p) => !people.some((x) => x.id === p.id)).slice(0, RESULTS_SHOWN);
  const picked = people.length + groups.length;
  const after = { ...list, groups: [...list.groups, ...groups.map((g) => ({ id: g.id, name: g.name, members: g.member_group_members.length }))],
    people: [...list.people, ...people.filter((p) => !invited.has(p.id)).map((p) => ({ source: 'person' as const, id: p.id }))] } as GuestList;

  async function addPeople() {
    setBusy(true);
    setError(null);
    try {
      const done = await invitePeople(event.id, people.map((p) => p.id), groups.map((g) => g.id));
      const total = done.people + done.groups;
      const who = people.map((p) => p.display_name.split(' ')[0]).concat(groups.map((g) => g.name)).join(', ');
      setNote(total ? `${who} : invités, prévenus dans Party` : 'Déjà invités');
      setPeople([]);
      setGroups([]);
      setSearch('');
      onInvited();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const names = people.map((p) => p.display_name.split(' ')[0]).concat(groups.map((g) => g.name));

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={st.overlay}>
        <View style={st.sheet} accessibilityViewIsModal accessibilityLabel={`Inviter à ${event.title}`}>
          <View style={st.grabber} />
          <View style={st.head}>
            <View style={{ flex: 1 }}>
              <T weight="bold" size={20} numberOfLines={1}>Inviter</T>
              <T muted size={13} numberOfLines={1}>À {event.title}, et seulement à cet événement.</T>
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel="Fermer" hitSlop={8} onPress={onClose} style={st.close}>
              <T weight="bold" color={colors.textSoft}>✕</T>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ gap: 18, paddingBottom: 32 }} keyboardShouldPersistTaps="handled">
            {headline ? (
              <View style={st.headline} accessibilityRole="header">
                <T weight="bold" size={17}>{headline}</T>
              </View>
            ) : null}
            {/* 1. Le lien, prêt à partager */}
            <View style={st.linkCard}>
              <T weight="bold" size={17}>🔗 Envoyer le lien</T>
              <T size={13} color={colors.textSoft}>Même sans l’app : la personne répond depuis le lien, en quelques secondes.</T>
              <Segmented options={[{ key: 'one', label: 'Une personne' }, { key: 'several', label: 'Plusieurs' }]} value={mode}
                onChange={(m) => { setMode(m); reset(); }} />
              {mode === 'one' ? (
                <View style={{ gap: 4 }}>
                  <Input accessibilityLabel="Pour qui ? (facultatif)" placeholder="Pour qui ? Prénom (facultatif)" value={label} maxLength={40}
                    onChangeText={(v) => { setLabel(v); reset(); }} autoCapitalize="words" />
                  <T muted size={12}>Le lien ne sert qu’à cette personne. Tu verras quand elle l’ouvre et ce qu’elle répond.</T>
                </View>
              ) : (
                <View style={st.stepperRow}>
                  <View style={{ flex: 1 }}>
                    <T weight="semibold" size={15}>Nombre de places</T>
                    <T muted size={12}>Les {places} premiers qui répondent ; ensuite le lien se ferme.</T>
                  </View>
                  <Stepper value={places} onChange={(n) => { setPlaces(n); reset(); }} />
                </View>
              )}
              <View style={{ gap: 6 }}>
                <T weight="semibold" size={13} color={colors.textSoft}>Valable jusqu’au</T>
                <View style={st.chips}>
                  {([['event', event.starts_at ? 'Après l’événement' : '14 jours'], ['3d', '3 jours'], ['7d', '7 jours']] as [Until, string][]).map(([k, l]) => (
                    <Pressable key={k} accessibilityRole="radio" accessibilityState={{ checked: until === k }} aria-checked={until === k}
                      onPress={() => { setUntil(k); reset(); }} style={[st.chip, until === k && st.chipOn]}>
                      <T size={13} weight="semibold" color={until === k ? colors.onAction : colors.textSoft}>{l}</T>
                    </Pressable>
                  ))}
                </View>
              </View>
              <View style={st.bubble}>
                <T size={13} color={colors.text}>{message(link ?? 'party.bobycharbon.ch/events/invite/…')}</T>
              </View>
              {link ? <T size={12} muted numberOfLines={1}>✓ Lien prêt : {link.replace(/^https?:\/\//, '')}</T> : null}
              <Button label="Partager le lien…" loading={busy} onPress={() => void send('share')} />
              <View style={st.shareRow}>
                {([['whatsapp', '💬', 'WhatsApp'], ['sms', '✉︎', 'Messages'], ['qr', '▦', 'QR code'], ['copy', '⧉', 'Copier']] as const).map(([k, icon, l]) => (
                  <Pressable key={k} accessibilityRole="button" accessibilityLabel={l} disabled={busy} onPress={() => void send(k)}
                    style={({ pressed }) => [st.shareBtn, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
                    <T size={20}>{icon}</T>
                    <T size={11} weight="semibold" color={colors.textSoft}>{l}</T>
                  </Pressable>
                ))}
              </View>
              {link ? <Button small variant="ghost" label="Nouveau lien (pour quelqu’un d’autre)" onPress={() => { reset(); setLabel(''); }} /> : null}
            </View>

            {/* 2. Des gens de Party, même hors du groupe, ou un groupe */}
            <View style={{ gap: 10 }}>
              <T weight="bold" size={17}>Ajouter des gens de Party</T>
              <Input accessibilityLabel="Chercher une personne ou un groupe" placeholder="🔍 Un prénom, un surnom, un groupe…" value={search} onChangeText={setSearch} />
              {picked ? (
                <View style={st.chips}>
                  {groups.map((g) => <PickedChip key={g.id} label={`👥 ${g.name}`} onRemove={() => setGroups(groups.filter((x) => x.id !== g.id))} />)}
                  {people.map((p) => <PickedChip key={p.id} label={p.display_name} onRemove={() => setPeople(people.filter((x) => x.id !== p.id))} />)}
                </View>
              ) : null}
              {foundGroups.length ? <T size={12} weight="bold" color={colors.muted}>GROUPES</T> : null}
              {foundGroups.map((g) => (
                <ResultRow key={g.id} title={g.name} hint={`Groupe · ${g.member_group_members.length} personnes`} icon="👥"
                  onPress={() => setGroups([...groups, g])} />
              ))}
              {foundPeople.length ? <T size={12} weight="bold" color={colors.muted}>PERSONNES</T> : null}
              {foundPeople.map((p) => {
                const already = invited.has(p.id);
                return (
                  <ResultRow key={p.id} title={p.display_name} person={p} disabled={already}
                    hint={inVip.has(p.id) ? `Déjà invité · ${list.vip_name ?? 'Vendredi Party'}` : already ? 'Déjà invité' : list.vip ? `Pas dans ${list.vip_name ?? 'Vendredi Party'}` : 'Sur Party'}
                    onPress={() => setPeople([...people, p])} />
                );
              })}
              {q && !matches.length && !foundGroups.length ? (
                <Pressable accessibilityRole="button" onPress={() => { setMode('one'); setLabel(search.trim()); reset(); setSearch(''); }} style={st.notFound}>
                  <T size={14} weight="semibold">« {search.trim()} » n’est pas sur Party ?</T>
                  <T size={13} color={colors.accent} weight="semibold">Envoie-lui un lien pour une personne ›</T>
                </Pressable>
              ) : null}
              {picked ? <Button label={`Inviter ${names.join(', ')}`} loading={busy} onPress={() => void addPeople()} /> : null}
            </View>

            {/* 3. La règle, en une phrase */}
            <View style={st.rule}>
              <T weight="bold" size={15}>{ruleSentence(after)}</T>
              <T muted size={13}>
                {names.length ? `${names.join(', ')} ${names.length > 1 ? 'voient' : 'voit'} l’événement` : 'Les invités voient l’événement'} sans entrer dans le groupe.
                {' Ils reçoivent une notification Party s’ils ont l’app.'}
              </T>
            </View>
            <ErrorText error={error} />
          </ScrollView>
        </View>
        {qr && link ? <QrOverlay url={link} title={event.title} when={when} places={mode === 'several' ? places : 1} onClose={() => setQr(false)} /> : null}
        {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
      </View>
    </Modal>
  );
}

function Stepper({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <View style={st.stepper}>
      <Pressable accessibilityRole="button" accessibilityLabel="Une place de moins" disabled={value <= 2} onPress={() => onChange(value - 1)} style={st.stepBtn}>
        <T size={20} weight="bold" color={value <= 2 ? colors.muted : colors.text}>−</T>
      </Pressable>
      <T size={17} weight="bold" style={{ minWidth: 28, textAlign: 'center' }}>{value}</T>
      <Pressable accessibilityRole="button" accessibilityLabel="Une place de plus" disabled={value >= MAX_PLACES} onPress={() => onChange(value + 1)} style={st.stepBtn}>
        <T size={20} weight="bold" color={value >= MAX_PLACES ? colors.muted : colors.text}>+</T>
      </Pressable>
    </View>
  );
}

function PickedChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Retirer ${label}`} onPress={onRemove} style={[st.chip, st.chipOn]}>
      <T size={13} weight="bold" color={colors.onAction} numberOfLines={1}>{label}  ✕</T>
    </Pressable>
  );
}

function ResultRow({ title, hint, icon, person, disabled, onPress }: {
  title: string; hint: string; icon?: string; person?: Person; disabled?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Ajouter ${title}`} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
      style={({ pressed }) => [st.result, disabled && { opacity: 0.5 }, pressed && { backgroundColor: colors.fill }]}>
      {person ? <Avatar id={person.id} name={person.display_name} photo={person.avatar_url} size={36} profile={false} />
        : <View style={st.resultIcon}><T size={17}>{icon}</T></View>}
      <View style={{ flex: 1, minWidth: 0 }}>
        <T weight="semibold" size={15} numberOfLines={1}>{title}</T>
        <T muted size={12} numberOfLines={1}>{hint}</T>
      </View>
      <T size={20} color={disabled ? colors.muted : colors.accent}>{disabled ? '✓' : '＋'}</T>
    </Pressable>
  );
}

/** QR code pour quelqu'un en face : l'appareil photo du téléphone ouvre l'invitation, sans app. */
function QrOverlay({ url, title, when, places, onClose }: { url: string; title: string; when: string | null; places: number; onClose: () => void }) {
  return (
    <View style={st.qrOverlay} accessibilityViewIsModal accessibilityLabel="QR code de l’invitation">
      <View style={st.qrCard}>
        <T weight="bold" size={20} style={{ textAlign: 'center' }}>Montre ce code</T>
        <T muted size={13} style={{ textAlign: 'center' }} numberOfLines={2}>{title}{when ? ` · ${when}` : ''}</T>
        <Image source={{ uri: qrDataUri(url) }} style={st.qr} accessibilityLabel="QR code du lien d’invitation" />
        <T size={13} weight="semibold" color={colors.textSoft} style={{ textAlign: 'center' }}>
          {places > 1 ? `👥 Pour plusieurs · ${places} places` : '🔗 Pour une personne'}
        </T>
        <T muted size={12} style={{ textAlign: 'center' }}>La personne vise le code avec l’appareil photo et répond. Pas besoin de l’app.</T>
        <Button label="Fermer" variant="secondary" onPress={onClose} />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(8,5,20,0.6)', justifyContent: 'flex-end' },
  sheet: { maxHeight: '94%', backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, borderWidth: 1,
    borderColor: colors.line, paddingHorizontal: 16, paddingTop: 8, width: '100%', maxWidth: 640, alignSelf: 'center' },
  grabber: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: colors.lineStrong, marginBottom: 10 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 14 },
  close: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center' },
  headline: { padding: 14, borderRadius: radius.md, backgroundColor: colors.accentDim, borderWidth: 1, borderColor: '#5A2346' },
  linkCard: { gap: 12, padding: 16, borderRadius: radius.lg, backgroundColor: colors.accentDim, borderWidth: 1, borderColor: '#5A2346' },
  stepperRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 4, padding: 3, borderRadius: radius.pill, backgroundColor: colors.fillStrong },
  stepBtn: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { minHeight: 36, paddingHorizontal: 12, borderRadius: radius.pill, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center', maxWidth: '100%' },
  chipOn: { backgroundColor: colors.action },
  bubble: { padding: 12, borderRadius: 16, borderBottomLeftRadius: 4, backgroundColor: colors.surface2 },
  shareRow: { flexDirection: 'row', gap: 8 },
  shareBtn: { flex: 1, minHeight: 60, borderRadius: radius.md, backgroundColor: colors.fillStrong, alignItems: 'center', justifyContent: 'center', gap: 2 },
  result: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, paddingHorizontal: 6, borderRadius: radius.md },
  resultIcon: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.lavenderDim, alignItems: 'center', justifyContent: 'center' },
  notFound: { gap: 4, padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, borderStyle: 'dashed' },
  rule: { gap: 4, padding: 14, borderRadius: radius.md, backgroundColor: colors.surface },
  qrOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(8,5,20,0.85)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  qrCard: { width: '100%', maxWidth: 360, gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: colors.surface },
  qr: { width: 240, height: 240, alignSelf: 'center', borderRadius: 12 },
});
