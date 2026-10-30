import { supabase } from './supabase';

export const CHAT_PHOTOS = 'chat-photos';
export const REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🔥'] as const;
const MAX_SIDE = 1600;
const MAX_SOURCE = 30 * 1024 * 1024;

export type NotifyLevel = 'all' | 'mentions' | 'none';
export type ChatSummary = {
  id: string; name: string; system: boolean; member: boolean; admin: boolean; creator: boolean;
  members: number; notify: NotifyLevel; last_at: string | null; last: string | null; unread: number;
};
export type GroupMessage = {
  id: string; group_id: string; user_id: string; body: string; photo_path: string | null; reply_to: string | null;
  mentions: string[]; mention_all: boolean; pinned: boolean; created_at: string; edited_at: string | null;
  deleted_at: string | null; deleted_by_admin: boolean;
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

/** « @Léa » dans le texte → citation de Léa ; « @tout » → tout le groupe (réservé aux admins, revérifié par la base). */
export function mentionsIn(body: string, people: { id: string; display_name: string }[]): { mentions: string[]; all: boolean } {
  const lower = body.toLowerCase();
  const mentions = people.filter((p) => p.display_name && lower.includes(`@${p.display_name.toLowerCase()}`)).map((p) => p.id);
  return { mentions, all: /(^|\s)@tout(\s|$|[!?.,])/i.test(body) };
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
