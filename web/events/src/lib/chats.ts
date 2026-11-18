import { supabase } from './supabase';

export const CHAT_PHOTOS = 'chat-photos';
export const REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🔥'] as const;
const MAX_SIDE = 1600;
const MAX_SOURCE = 30 * 1024 * 1024;

export type NotifyLevel = 'all' | 'mentions' | 'none';
/** Qui peut écrire @tout dans un groupe : tous les membres, ou admins et organisateurs. */
export type EveryoneBy = 'all' | 'staff';
export type ChatSummary = {
  id: string; name: string; system: boolean; member: boolean; admin: boolean; creator: boolean;
  members: number; notify: NotifyLevel; last_at: string | null; last: string | null; unread: number;
  /** Message direct (conversation privée à deux, 4.11) : l'autre personne (nom = son pseudo, photo), bloquée par moi. */
  kind?: 'group' | 'direct'; user_id?: string; avatar_url?: string | null; blocked?: boolean;
  /** Groupe : son emoji et sa couleur (nouveau graphisme du 17.11). */
  emoji?: string; color?: string;
  /** Groupe : chemin de sa photo (group-photos), 17.11. */
  photo_path?: string | null;
};
/** Message direct tel que lu dans direct_messages, présenté comme un message de groupe (même bulle, même écran). */
export type DirectMessageRow = Omit<GroupMessage, 'group_id' | 'mentions' | 'mention_all' | 'deleted_by_admin' | 'announcement'> & { chat_id: string };
export function directAsGroupMessage(m: DirectMessageRow): GroupMessage {
  return { ...m, group_id: m.chat_id, mentions: [], mention_all: false, deleted_by_admin: false, announcement: false };
}
export type GroupMessage = {
  id: string; group_id: string; user_id: string; body: string; photo_path: string | null; reply_to: string | null;
  audio_path?: string | null; audio_seconds?: number | null; pending?: boolean;
  /** Pas parti (réseau absent) : gardé dans la bulle, « Toucher pour réessayer » (file d'envoi, outbox.ts). */
  failed?: boolean;
  mentions: string[]; mention_all: boolean; pinned: boolean; created_at: string; edited_at: string | null;
  deleted_at: string | null; deleted_by_admin: boolean;
  /** « @annonce » : épinglé d'office par la base, affiché en surbrillance en haut de la discussion. */
  announcement?: boolean;
  /** Discussions v2 (18.11) : soirée jointe (carte dans la bulle) ; message direct : citation d'un groupe / d'une soirée. */
  event_id?: string | null;
  /** Copie de la soirée (titre, date, lieu…) gardée par la base, même quand l'événement est supprimé. */
  event_card?: { id?: string | null; title?: string; start?: string | null; place?: string | null } | null;
  quote?: { from: 'group' | 'event'; title: string; author: string; excerpt: string } | null;
};
export type Reaction = { message_id: string; user_id: string; emoji: string };

/** Numéro montré dans le groupe → « +41790000001 » (affiché tel quel, lien tel: pour appeler d'un toucher). */
export function dialable(phone: string | null | undefined): string | null {
  const digits = (phone ?? '').replace(/[^\d]/g, '');
  return digits.length >= 6 ? `+${digits}` : null;
}

/** Texte d'un message supprimé, comme l'avis de l'admin le demande. */
export function deletedLabel(m: Pick<GroupMessage, 'deleted_by_admin'>): string {
  return m.deleted_by_admin ? 'Message supprimé par un admin' : 'Message supprimé';
}

/** Sans accents ni casse : « lea » trouve Léa (suggestions de l'@ et citations). */
export function fold(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

/** « @Léa » (ou « @lea ») dans le texte → citation de Léa ; « @tout » → tout le groupe (tout membre peut l'écrire). */
export function mentionsIn(body: string, people: { id: string; display_name: string }[]): { mentions: string[]; all: boolean } {
  const folded = fold(body);
  const mentions = people.filter((p) => p.display_name && folded.includes(`@${fold(p.display_name)}`)).map((p) => p.id);
  return { mentions, all: /(^|\s)@tout(\s|$|[!?.,])/i.test(body) };
}

/** « @annonce » (mot entier, sans casse) : la base épingle le message en annonce (même règle que guard_group_message). */
export function isAnnouncement(body: string): boolean {
  return /(^|[^\p{L}\p{N}_])@annonce($|[^\p{L}\p{N}_])/iu.test(body);
}

export type MentionSuggestion = { key: string; label: string; hint: string; id: string | null; photo?: string | null };

/** Mots réservés proposés avec les membres : tout le groupe, annonce épinglée. */
const SPECIAL_TAGS: MentionSuggestion[] = [
  { key: 'tout', label: 'tout', hint: 'Tout le groupe', id: null },
  { key: 'annonce', label: 'annonce', hint: 'Annonce épinglée en haut du groupe', id: null },
];
const MAX_SUGGESTIONS = 6;

/** Ce qui suit l'@ en cours de frappe (avant le curseur) ; null quand on n'est pas en train de citer. */
export function mentionQuery(text: string, cursor: number = text.length): string | null {
  const match = /(^|\s)@([^\s@]*)$/.exec(text.slice(0, cursor));
  return match ? match[2] : null;
}

/** Ce que je peux écrire dans ce groupe : @tout (choix du groupe), @annonce (admins et organisateurs). */
export type MentionRights = { everyone: boolean; announce: boolean;
  /** Discussion d'un événement : les citations de l'organisation (@toutlemonde, @present, @annonce) à la place de
   * @tout et @annonce ; vide pour un invité. */
  tags?: MentionSuggestion[] };

/** Citations de l'organisation d'un événement (migration 20261116180000 : la base décide d'après le texte). */
export const EVENT_TAGS: MentionSuggestion[] = [
  { key: 'toutlemonde', label: 'toutlemonde', hint: 'Tout le monde : invités et participants', id: null },
  { key: 'present', label: 'present', hint: 'Les présents et les peut-être', id: null },
  { key: 'annonce', label: 'annonce', hint: 'Annonce épinglée en haut, envoyée à tous', id: null },
];

/** @toutlemonde, @present (@présents…) ou @annonce dans le texte, même règle que la base (guard_message_change). */
export function eventTag(body: string): string | null {
  for (const tag of ['toutlemonde', 'pr[eé]sents?', 'annonce']) {
    if (new RegExp(`(^|[^\\p{L}\\p{N}_])@${tag}($|[^\\p{L}\\p{N}_])`, 'iu').test(body)) return tag;
  }
  return null;
}

/** Texte d'une bulle découpé : les « @surnom » des membres et les citations spéciales à part (gras, couleur). */
export function mentionParts(body: string, names: string[]): { text: string; mention: boolean }[] {
  const words = [...new Set([...names, 'toutlemonde', 'tout', 'présents', 'presents', 'présent', 'present', 'annonce']
    .filter(Boolean).map(fold))].sort((a, b) => b.length - a.length);
  const parts: { text: string; mention: boolean }[] = [];
  let plain = '';
  let i = 0;
  while (i < body.length) {
    if (body[i] === '@' && (i === 0 || !/[\p{L}\p{N}_]/u.test(body[i - 1]))) {
      const word = words.find((w) => fold(body.slice(i + 1, i + 1 + w.length)) === w
        && !/[\p{L}\p{N}_]/u.test(body[i + 1 + w.length] ?? ' '));
      if (word) {
        if (plain) parts.push({ text: plain, mention: false });
        plain = '';
        parts.push({ text: body.slice(i, i + 1 + word.length), mention: true });
        i += 1 + word.length;
        continue;
      }
    }
    plain += body[i];
    i += 1;
  }
  if (plain) parts.push({ text: plain, mention: false });
  return parts;
}

/** « @annonce » retiré du texte d'une annonce (la carte le dit déjà). */
export function withoutAnnounceTag(body: string): string {
  return body.replace(/(^|\s)@annonce(?=$|[^\p{L}\p{N}_])/giu, '$1').trim();
}

/** Fil façon WhatsApp : un séparateur par jour, et les messages d'une même personne regroupés (même jour, moins de
 * 5 min, pas une annonce) : nom en tête de la série, photo en bas. */
export type TimelineRow<M> = { key: string; day: string } | { key: string; message: M; first: boolean; last: boolean };
const SERIES_MS = 5 * 60 * 1000;
type TimelineMessage = { id: string; user_id: string; created_at: string; announcement?: boolean; pinned?: boolean };

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function joins(a: TimelineMessage | undefined, b: TimelineMessage | undefined): boolean {
  if (!a || !b || a.user_id !== b.user_id) return false;
  if ((a.announcement && a.pinned) || (b.announcement && b.pinned)) return false;
  const da = new Date(a.created_at), db = new Date(b.created_at);
  return sameDay(da, db) && Math.abs(db.getTime() - da.getTime()) < SERIES_MS;
}

export function dayLabel(date: Date, now: Date = new Date()): string {
  if (sameDay(date, now)) return 'Aujourd’hui';
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return 'Hier';
  const weekAgo = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6);
  if (date >= weekAgo && date <= now) {
    const day = date.toLocaleDateString('fr-CH', { weekday: 'long' });
    return day.charAt(0).toUpperCase() + day.slice(1);
  }
  return date.toLocaleDateString('fr-CH', date.getFullYear() === now.getFullYear()
    ? { day: 'numeric', month: 'long' } : { day: 'numeric', month: 'long', year: 'numeric' });
}

export function chatTimeline<M extends TimelineMessage>(messages: M[], now: Date = new Date()): TimelineRow<M>[] {
  const rows: TimelineRow<M>[] = [];
  let day: Date | null = null;
  messages.forEach((m, i) => {
    const date = new Date(m.created_at);
    if (!day || !sameDay(day, date)) {
      day = date;
      rows.push({ key: `day-${m.id}`, day: dayLabel(date, now) });
    }
    rows.push({ key: m.id, message: m, first: !joins(messages[i - 1], m), last: !joins(m, messages[i + 1]) });
  });
  return rows;
}

/** Couleur du nom d'un auteur : stable, lisible sur fond sombre (même palette que l'app iPhone). */
const NAME_COLORS = ['#BAA6FF', '#73D9F2', '#FF9E73', '#8CE68C', '#FF8CBF', '#FFD166', '#80B3FF', '#D99AF2'];
export function nameColor(id: string): string {
  let sum = 5381;
  for (const c of id) sum = ((sum * 33) + c.codePointAt(0)!) >>> 0;
  return NAME_COLORS[sum % NAME_COLORS.length];
}

/** Membres du groupe (moi exclu) dont le surnom (ou un de ses mots) commence par les lettres tapées, puis @tout et
 * @annonce quand j'y ai droit. */
export function mentionSuggestions(query: string, people: { id: string; display_name: string; avatar_url?: string | null }[],
  rights: MentionRights = { everyone: true, announce: true },
  /** App iPhone : noms de mes contacts (id → nom) ; « @mar » trouve aussi le membre enregistré « Marie ». */
  contacts: Record<string, string> = {}): MentionSuggestion[] {
  const q = fold(query);
  const starts = (name: string) => fold(name).startsWith(q) || fold(name).split(/[\s.\-_]+/).some((w) => w.startsWith(q));
  const members = people.filter((p) => p.display_name && (starts(p.display_name) || (contacts[p.id] ? starts(contacts[p.id]) : false)))
    .sort((a, b) => Number(!fold(a.display_name).startsWith(q)) - Number(!fold(b.display_name).startsWith(q))
      || a.display_name.localeCompare(b.display_name, 'fr'))
    .map((p) => ({ key: p.id, label: p.display_name, hint: contacts[p.id] ?? '', id: p.id, photo: p.avatar_url ?? null }));
  const specials = (rights.tags ?? SPECIAL_TAGS.filter((t) => (t.key === 'tout' ? rights.everyone : rights.announce)))
    .filter((t) => fold(t.label).startsWith(q));
  return [...members.slice(0, MAX_SUGGESTIONS - specials.length), ...specials];
}

/** Remplace l'@ en cours par « @Surnom » suivi d'une espace ; renvoie le texte et la place du curseur. */
export function insertMention(text: string, cursor: number, label: string): { text: string; cursor: number } {
  const before = text.slice(0, cursor);
  const at = before.lastIndexOf('@');
  if (at < 0) return { text, cursor };
  const head = `${before.slice(0, at)}@${label} `;
  const rest = text.slice(cursor).replace(/^\S*/, '').replace(/^ /, '');
  return { text: head + rest, cursor: head.length };
}

/** Choisir une photo (site : sélecteur du navigateur). */
export function pickPhoto(): Promise<File | null> {
  return new Promise((resolve) => {
    if (typeof document === 'undefined') return resolve(null);
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = () => resolve(input.files?.[0] ?? null);
    input.click();
  });
}

/** Photo réduite (1600 px au plus, JPEG) avant l'envoi : rapide, et l'espace de stockage reste petit. */
export async function shrinkPhoto(file: File): Promise<Blob> {
  if (file.size > MAX_SOURCE) throw new Error('Photo trop volumineuse.');
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) throw new Error('Cette photo n’a pas pu être lue.');
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Photo illisible.'))), 'image/jpeg', 0.82));
}

/** Envoie la photo dans le dossier du groupe (seuls ses membres peuvent l'envoyer et la voir). */
export async function uploadChatPhoto(groupId: string, photo: Blob): Promise<string> {
  const path = `${groupId}/${Date.now()}-${Math.random().toString(36).slice(2)}.jpg`;
  const { error } = await supabase.storage.from(CHAT_PHOTOS).upload(path, photo, { contentType: 'image/jpeg', upsert: false });
  if (error) throw new Error('La photo n’a pas pu être envoyée. Réessaie.');
  return path;
}

/** Liens temporaires des photos affichées (une seule demande pour toute la page). */
export async function signedPhotos(paths: string[]): Promise<Map<string, string>> {
  const unique = [...new Set(paths)];
  if (!unique.length) return new Map();
  const { data } = await supabase.storage.from(CHAT_PHOTOS).createSignedUrls(unique, 3600);
  return new Map((data ?? []).flatMap((d) => (d.signedUrl && d.path ? [[d.path, d.signedUrl] as [string, string]] : [])));
}

/** Identifiant choisi ici : le message s'affiche tout de suite et garde sa place une fois enregistré. */
export function newMessageId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    return (c === 'x' ? r : (r % 4) + 8).toString(16);
  });
}

export function voiceClock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** Enregistrement d'un vocal (navigateur) : micro du téléphone de préférence, jamais un casque Bluetooth s'il y a le choix.
 * AAC (mp4) quand le navigateur sait le faire (lu partout, iPhone compris), sinon Opus (webm). */
export type VoiceRecording = { stop: (send: boolean) => Promise<{ blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null> };

const BLUETOOTH = /bluetooth|airpods|headset|hands-?free|buds|bt\b/i;

export async function startVoice(): Promise<VoiceRecording> {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    throw new Error('Ce navigateur ne sait pas enregistrer de message vocal.');
  }
  let stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  // Les noms des micros ne sont lisibles qu'après l'autorisation : on passe au micro intégré si un Bluetooth a été pris.
  const current = stream.getAudioTracks()[0]?.label ?? '';
  if (BLUETOOTH.test(current)) {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const builtIn = devices.find((d) => d.kind === 'audioinput' && d.deviceId !== 'default' && !BLUETOOTH.test(d.label));
    if (builtIn) {
      stream.getTracks().forEach((t) => t.stop());
      stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: builtIn.deviceId } } });
    }
  }
  const type = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm';
  const recorder = new MediaRecorder(stream, { mimeType: type, audioBitsPerSecond: 48_000 });
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  const started = Date.now();
  recorder.start(250);
  return {
    stop: (send) => new Promise((resolve) => {
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const seconds = (Date.now() - started) / 1000;
        resolve(send && seconds >= 0.6 ? { blob: new Blob(chunks, { type }), seconds, ext: type === 'audio/mp4' ? 'm4a' : 'webm' } : null);
      };
      recorder.stop();
    }),
  };
}

export async function uploadChatAudio(groupId: string, audio: { blob: Blob; ext: 'm4a' | 'webm' }): Promise<string> {
  const rand = Array.from({ length: 10 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
  const path = `${groupId}/${Date.now()}-${rand}.${audio.ext}`;
  const { error } = await supabase.storage.from(CHAT_PHOTOS).upload(path, audio.blob, {
    contentType: audio.ext === 'm4a' ? 'audio/mp4' : 'audio/webm', upsert: false });
  if (error) throw new Error('Le message vocal n’a pas pu être envoyé. Réessaie.');
  return path;
}
