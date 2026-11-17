import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Image, Pressable, ScrollView, View } from 'react-native';

import { EventCover, type EventChatCard } from './chat/EventChatTitle';
import { LinkedText } from './LinkedText';
import { ReportSheet } from './ReportSheet';
import { Avatar, Button, ConfirmButton, ErrorText, Field, Input, Section, Segmented, T } from './ui';
import { authorOf, eventChatMedia, eventChatSearch, isMuted, MUTE_CHOICES, muteLabel, NOTIFY_LEVELS, saveEventChatSettings, signedPhotos,
  type ChatWriteMode, type EventChatHit, type EventChatMedia, type MuteChoice, type NotifyLevel } from '@/lib/chats';
import { formatLongDay, formatMessageTime, formatTime, plural } from '@/lib/format';
import { duration, enter, transition } from '@/lib/motion';
import { setBlocked, type ReportTarget } from '@/lib/moderation';
import { colors, radius } from '@/lib/theme';

export type EventPerson = { id: string; name: string; photo: string | null; rsvp: string | null; organizer: boolean; invited: boolean };
export type EventPin = { id: string; author: string; text: string; at: string; announcement: boolean };

type Props = {
  eventId: string;
  me: string;
  /** Organisation de l'événement (ou admin) : réglages de la discussion ; invités sans réponse visibles. */
  staff: boolean;
  card: EventChatCard;
  people: EventPerson[];
  level: NotifyLevel;
  mutedUntil: string | null;
  writeMode: ChatWriteMode;
  pins: EventPin[];
  /** Personnes que j'ai bloquées. */
  blocked: Set<string>;
  nameOf: (id: string) => string | null;
  onLevel: (level: NotifyLevel) => void;
  onMute: (choice: MuteChoice | null) => void;
  /** Montrer un message dans le fil (épinglé, résultat de recherche, média). */
  onJump: (messageId: string, at: string) => void;
  onChanged: () => void;
};

const SEARCH_DELAY_MS = 300;
const DESCRIPTION_MAX = 500;

/** Infos de la discussion d'un événement, façon « Infos du groupe » de WhatsApp : grande couverture, titre, date et lieu,
 * description, notifications et sourdine, médias / liens / vocaux, messages épinglés, recherche, participants par réponse
 * (les invités sans réponse ne sont listés qu'à l'organisation : event_chat_people, règle du 11.11), réglages de
 * l'organisation (Qui peut écrire, Description), Signaler / Bloquer (modération commune). */
export function EventChatSettings({ eventId, me, staff, card, people, level, mutedUntil, writeMode, pins, blocked, nameOf,
  onLevel, onMute, onJump, onChanged }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportTarget | null>(null);
  const [openPerson, setOpenPerson] = useState<string | null>(null);
  const muted = muteLabel(mutedUntil);

  const rest = people.filter((p) => !p.organizer);
  const buckets = [
    { title: 'Organisation', list: people.filter((p) => p.organizer) },
    { title: 'Présents', list: rest.filter((p) => p.rsvp === 'yes') },
    { title: 'Peut-être', list: rest.filter((p) => p.rsvp === 'maybe') },
    { title: 'Pas présents', list: rest.filter((p) => p.rsvp === 'no') },
    { title: 'Invités sans réponse', list: rest.filter((p) => !p.rsvp && p.invited) },
    { title: 'Autres personnes de la discussion', list: rest.filter((p) => !p.rsvp && !p.invited) },
  ].filter((b) => b.list.length);

  async function block(id: string, next: boolean) {
    setError(null);
    try {
      await setBlocked(id, next);
      setOpenPerson(null);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Le blocage n’a pas pu être enregistré.');
    }
  }

  const when = card.starts_at ? `${formatLongDay(card.starts_at)} · ${formatTime(card.starts_at)}${card.ends_at ? ` – ${formatTime(card.ends_at)}` : ''}` : 'Date à définir';

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 16, paddingBottom: 48, width: '100%', maxWidth: 640, alignSelf: 'center' }}>
      {/* En-tête : grande couverture, titre, date, lieu, participants. */}
      <View style={[{ alignItems: 'center', gap: 8, paddingTop: 8 }, enter('rise')]}>
        <EventCover id={eventId} card={card} size={124} />
        <View accessibilityRole="header"><T weight="bold" size={22} style={{ textAlign: 'center' }}>{card.title}</T></View>
        <T muted style={{ textAlign: 'center' }}>📅 {when}</T>
        {card.place ? <T muted style={{ textAlign: 'center' }}>📍 {card.place}</T> : null}
        <T muted size={13}>{plural(card.going, 'participant')}{card.maybe ? ` · ${card.maybe} peut-être` : ''}</T>
        <View style={{ flexDirection: 'row', gap: 10, marginTop: 4 }}>
          <Button small variant="secondary" label="📄 Fiche de l’événement" onPress={() => router.push(`/event/${eventId}`)} />
        </View>
      </View>

      {card.description ? (
        <Section title="Description">
          <LinkedText text={card.description} />
          {!staff ? (
            <Button small variant="ghost" label="Signaler la description" style={{ alignSelf: 'flex-start' }}
              onPress={() => setReport({ kind: 'event', id: eventId, label: 'la description de la discussion' })} />
          ) : null}
        </Section>
      ) : null}

      <Section title="Notifications">
        <View accessibilityRole="radiogroup" accessibilityLabel="Notifications de la discussion" style={{ gap: 2 }}>
          {NOTIFY_LEVELS.map((l) => {
            const on = level === l.key;
            return (
              <Pressable key={l.key} accessibilityRole="radio" accessibilityState={{ checked: on }} accessibilityLabel={l.label}
                onPress={() => onLevel(l.key)}
                style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, paddingVertical: 6 }, pressed && { opacity: 0.7 }]}>
                <View style={[{ width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: on ? colors.accent : colors.lineStrong,
                  alignItems: 'center', justifyContent: 'center' }, transition('border-color', duration.fast)]}>
                  {on ? <View style={[{ width: 11, height: 11, borderRadius: 6, backgroundColor: colors.accent }, enter('pop')]} /> : null}
                </View>
                <View style={{ flex: 1 }}>
                  <T weight={on ? 'semibold' : 'body'}>{l.label}{l.key === 'mentions' ? <T muted size={12}>  (par défaut)</T> : null}</T>
                  <T muted size={12}>{l.hint}</T>
                </View>
              </Pressable>
            );
          })}
        </View>
        <View style={{ height: 1, backgroundColor: colors.line }} />
        <T weight="semibold">🔕 Sourdine</T>
        {muted ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <T muted style={{ flex: 1 }}>{muted}</T>
            <Button small variant="secondary" label="Réactiver" accessibilityLabel="Réactiver les notifications" onPress={() => onMute(null)} />
          </View>
        ) : (
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {MUTE_CHOICES.map((c) => (
              <Button key={c.key} small variant="secondary" label={c.label} accessibilityLabel={`Sourdine ${c.label}`} onPress={() => onMute(c.key)} />
            ))}
          </View>
        )}
        {level !== 'none' && !isMuted(mutedUntil) ? null
          : <T muted size={12}>Les messages arrivent toujours ici ; seules les notifications sont coupées.</T>}
      </Section>

      <MediaSection eventId={eventId} nameOf={nameOf} onJump={onJump} />

      {pins.length ? (
        <Section title={`Messages épinglés · ${pins.length}`}>
          {pins.map((p) => (
            <Pressable key={p.id} accessibilityRole="button" accessibilityLabel={`${p.announcement ? 'Annonce' : 'Épinglé'} : ${p.author}, ${p.text}`}
              onPress={() => onJump(p.id, p.at)}
              style={({ pressed }) => [{ flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 6 }, pressed && { opacity: 0.7 }]}>
              <T size={16}>{p.announcement ? '📣' : '📌'}</T>
              <View style={{ flex: 1 }}>
                <T size={13} weight="bold" color={colors.accentSoft} numberOfLines={1}>{p.author} · {formatMessageTime(p.at)}</T>
                <T size={14} numberOfLines={2}>{p.text}</T>
              </View>
            </Pressable>
          ))}
        </Section>
      ) : null}

      <SearchSection eventId={eventId} nameOf={nameOf} onJump={onJump} />

      {buckets.map((b) => (
        <Section key={b.title} title={`${b.title} · ${b.list.length}`}>
          {b.list.map((p) => (
            <View key={p.id}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 4 }}>
                <Pressable accessibilityRole="link" accessibilityLabel={`Profil de ${p.name}`} onPress={() => router.push(`/member/${p.id}`)}
                  style={({ pressed }) => [{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 }, pressed && { opacity: 0.7 }]}>
                  <Avatar id={p.id} name={p.name} photo={p.photo} size={38} profile={false} />
                  <View style={{ flex: 1 }}>
                    <T numberOfLines={1}>{p.name}</T>
                    {blocked.has(p.id) ? <T muted size={12}>Bloqué·e</T> : null}
                  </View>
                </Pressable>
                {p.id === me ? <T muted size={12}>Toi</T> : (
                  <Pressable accessibilityRole="button" accessibilityLabel={`Signaler ou bloquer ${p.name}`}
                    onPress={() => setOpenPerson((o) => (o === p.id ? null : p.id))}
                    style={({ pressed }) => [{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 22 }, pressed && { backgroundColor: colors.fill }]}>
                    <T muted size={18}>⋯</T>
                  </Pressable>
                )}
              </View>
              {openPerson === p.id ? (
                <View style={[{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', paddingLeft: 50, paddingBottom: 6 }, enter('drop')]}>
                  <Button small variant="secondary" label={`Signaler ${p.name}`} onPress={() => setReport({ kind: 'profile', id: p.id, label: `le profil de ${p.name}` })} />
                  {blocked.has(p.id)
                    ? <Button small variant="secondary" label={`Débloquer ${p.name}`} onPress={() => void block(p.id, false)} />
                    : <ConfirmButton small label={`Bloquer ${p.name}`} confirmLabel="Confirmer le blocage" onConfirm={() => block(p.id, true)} />}
                </View>
              ) : null}
            </View>
          ))}
        </Section>
      ))}
      {!buckets.length ? <T muted>Personne pour l’instant.</T> : null}
      <ErrorText error={error} />

      {staff ? <OrganizerSettings eventId={eventId} writeMode={writeMode} description={card.description} onChanged={onChanged} /> : null}

      <ReportSheet target={report} onClose={() => setReport(null)} />
    </ScrollView>
  );
}

/** Réglages de l'organisation (organisateurs, co-organisateurs, admins ; la base vérifie) : qui écrit, description. */
function OrganizerSettings({ eventId, writeMode, description, onChanged }: { eventId: string; writeMode: ChatWriteMode; description: string | null; onChanged: () => void }) {
  const [mode, setMode] = useState<ChatWriteMode>(writeMode);
  const [text, setText] = useState(description ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  // Réglage changé ailleurs (relu de la base) : le choix affiché le suit.
  const [seenMode, setSeenMode] = useState(writeMode);
  if (seenMode !== writeMode) {
    setSeenMode(writeMode);
    setMode(writeMode);
  }

  async function changeMode(next: ChatWriteMode) {
    const before = mode;
    setMode(next);
    setError(null);
    try {
      await saveEventChatSettings(eventId, { write: next });
      onChanged();
    } catch (e) {
      setMode(before);
      setError(e instanceof Error ? e.message : 'Le réglage n’a pas pu être enregistré.');
    }
  }

  async function saveDescription() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await saveEventChatSettings(eventId, { description: text.trim() });
      setSaved(true);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La description n’a pas pu être enregistrée.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Réglages de l’organisation">
      <T weight="semibold">Qui peut écrire</T>
      <Segmented options={[{ key: 'all' as ChatWriteMode, label: 'Tout le monde' }, { key: 'staff' as ChatWriteMode, label: 'Organisation seulement' }]}
        value={mode} onChange={(k) => void changeMode(k)} />
      <T muted size={12}>{mode === 'staff' ? 'Les invités lisent et réagissent ; seule l’organisation envoie des messages.' : 'Tous les invités qui ont accès à la discussion peuvent écrire.'}</T>
      <Field label="Description de la discussion" value={text} onChangeText={(v) => { setText(v); setSaved(false); }} multiline maxLength={DESCRIPTION_MAX}
        placeholder="Infos pratiques, règles, programme…" hint={`${text.length}/${DESCRIPTION_MAX}`} />
      <Button small label={saved ? 'Description enregistrée ✓' : 'Enregistrer la description'} loading={busy}
        disabled={text.trim() === (description ?? '').trim()} onPress={() => void saveDescription()} />
      <ErrorText error={error} />
      <View style={{ height: 1, backgroundColor: colors.line }} />
      <T size={14}>👥 <T size={14} weight="bold">@toutlemonde</T> prévient tous les invités et participants.</T>
      <T size={14}>✅ <T size={14} weight="bold">@present</T> prévient les présents et les peut-être.</T>
      <T size={14}>📣 <T size={14} weight="bold">Annonce</T> (bouton 📣 ou @annonce) : épinglée en haut, envoyée à tous.</T>
      <T muted size={13}>Tu peux aussi épingler un message, ou retirer celui d’un autre, depuis ses actions (appui long ou ⋯).</T>
    </Section>
  );
}

type MediaTab = 'photo' | 'link' | 'audio';

/** Médias, liens et vocaux de la discussion (event_chat_media), du plus récent au plus ancien ; un toucher montre le message. */
function MediaSection({ eventId, nameOf, onJump }: { eventId: string; nameOf: (id: string) => string | null; onJump: (id: string, at: string) => void }) {
  const [items, setItems] = useState<EventChatMedia[] | null>(null);
  const [urls, setUrls] = useState<Map<string, string>>(new Map());
  const [tab, setTab] = useState<MediaTab>('photo');
  const [more, setMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load(before: string | null) {
    eventChatMedia(eventId, before).then(async (page) => {
      setItems((prev) => [...(before ? prev ?? [] : []), ...page]);
      setMore(page.length >= 60);
      const paths = page.filter((m) => m.kind !== 'link' && m.path && !m.url).map((m) => m.path!);
      const signed = await signedPhotos(paths).catch(() => new Map<string, string>());
      if (signed.size) setUrls((prev) => new Map([...prev, ...signed]));
    }).catch((e: unknown) => {
      setError(e instanceof Error ? e.message : 'Les médias n’ont pas pu être lus.');
      setItems((prev) => prev ?? []);
    });
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- une lecture à l'ouverture
  useEffect(() => load(null), [eventId]);

  const shown = (items ?? []).filter((m) => m.kind === tab);
  const urlOf = (m: EventChatMedia) => m.url ?? (m.path ? urls.get(m.path) ?? null : null);
  const counts = { photo: 0, link: 0, audio: 0 };
  for (const m of items ?? []) counts[m.kind] = (counts[m.kind] ?? 0) + 1;

  return (
    <Section title="Médias, liens et vocaux">
      <Segmented options={[{ key: 'photo' as MediaTab, label: `Photos${counts.photo ? ` · ${counts.photo}` : ''}` },
        { key: 'link' as MediaTab, label: `Liens${counts.link ? ` · ${counts.link}` : ''}` },
        { key: 'audio' as MediaTab, label: `Vocaux${counts.audio ? ` · ${counts.audio}` : ''}` }]} value={tab} onChange={setTab} />
      {items === null ? <T muted>Chargement…</T> : !shown.length ? (
        <T muted>{tab === 'photo' ? 'Aucune photo pour l’instant.' : tab === 'link' ? 'Aucun lien pour l’instant.' : 'Aucun vocal pour l’instant.'}</T>
      ) : tab === 'photo' ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
          {shown.map((m) => (
            <Pressable key={m.message_id} accessibilityRole="button" accessibilityLabel={`Photo de ${authorOf(m, nameOf) || 'quelqu’un'}, voir le message`}
              onPress={() => onJump(m.message_id, m.at)} style={({ pressed }) => [{ width: '32.4%', aspectRatio: 1 }, pressed && { opacity: 0.75 }]}>
              {urlOf(m) ? <Image source={{ uri: urlOf(m)! }} resizeMode="cover" style={{ width: '100%', height: '100%', borderRadius: 8, backgroundColor: colors.surface2 }} />
                : <View style={{ flex: 1, borderRadius: 8, backgroundColor: colors.surface2 }} />}
            </Pressable>
          ))}
        </View>
      ) : (
        <View style={{ gap: 4 }}>
          {shown.map((m) => (
            <View key={`${m.message_id}-${m.url ?? m.path}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }}>
              <T size={18}>{tab === 'link' ? '🔗' : '🎤'}</T>
              <View style={{ flex: 1, minWidth: 0 }}>
                {tab === 'link' && m.url ? <LinkedText text={m.url} numberOfLines={1} /> : <T numberOfLines={1}>{m.text || 'Message vocal'}</T>}
                <T muted size={12} numberOfLines={1}>{authorOf(m, nameOf)}{authorOf(m, nameOf) ? ' · ' : ''}{formatMessageTime(m.at)}</T>
              </View>
              <Button small variant="ghost" label="Voir" accessibilityLabel="Voir le message" onPress={() => onJump(m.message_id, m.at)} />
            </View>
          ))}
        </View>
      )}
      {more && items?.length ? <Button small variant="secondary" label="Plus anciens" onPress={() => void load(items[items.length - 1].at)} /> : null}
      <ErrorText error={error} />
    </Section>
  );
}

/** Rechercher dans la discussion (event_chat_search : 50 résultats au plus, sans messages supprimés ni de personnes bloquées). */
function SearchSection({ eventId, nameOf, onJump }: { eventId: string; nameOf: (id: string) => string | null; onJump: (id: string, at: string) => void }) {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<EventChatHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const turn = useRef(0);
  const query = q.trim();
  useEffect(() => {
    if (query.length < 2) return;
    const mine = ++turn.current;
    const timer = setTimeout(() => {
      eventChatSearch(eventId, query)
        .then((r) => { if (turn.current === mine) { setHits(r); setError(null); } })
        .catch((e) => { if (turn.current === mine) setError(e instanceof Error ? e.message : 'La recherche n’a pas pu aboutir.'); });
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query, eventId]);
  // Moins de 2 lettres : rien d'affiché (l'ancienne recherche reste en mémoire, cachée).
  const shownHits = query.length < 2 ? null : hits;
  const results = useMemo(() => shownHits ?? [], [shownHits]);

  return (
    <Section title="Rechercher">
      <Input accessibilityLabel="Rechercher dans la discussion" placeholder="🔍 Rechercher dans la discussion…" value={q} onChangeText={setQ}
        style={{ borderRadius: radius.pill }} />
      {shownHits !== null && !results.length ? <T muted>Aucun message trouvé.</T> : null}
      {results.map((h) => (
        <Pressable key={h.message_id} accessibilityRole="button" accessibilityLabel={`${authorOf(h, nameOf)} : ${h.snippet}, voir le message`}
          onPress={() => onJump(h.message_id, h.at)}
          style={({ pressed }) => [{ paddingVertical: 6, gap: 2 }, pressed && { opacity: 0.7 }]}>
          <T size={12} muted>{authorOf(h, nameOf)} · {formatMessageTime(h.at)}</T>
          <T size={14} numberOfLines={2}>{h.snippet}</T>
        </Pressable>
      ))}
      <ErrorText error={error} />
    </Section>
  );
}
