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
};
export type GroupMessage = {
  id: string; group_id: string; user_id: string; body: string; photo_path: string | null; reply_to: string | null;
  audio_path?: string | null; audio_seconds?: number | null; pending?: boolean;
  mentions: string[]; mention_all: boolean; pinned: boolean; created_at: string; edited_at: string | null;
  deleted_at: string | null; deleted_by_admin: boolean;
  /** « @annonce » : épinglé d'office par la base, affiché en surbrillance en haut de la discussion. */
  announcement?: boolean;
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
export type MentionRights = { everyone: boolean; announce: boolean };

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
  const specials = SPECIAL_TAGS.filter((t) => t.label.startsWith(q) && (t.key === 'tout' ? rights.everyone : rights.announce));
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
