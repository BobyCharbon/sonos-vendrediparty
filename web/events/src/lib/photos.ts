import { supabase } from './supabase';

export const PROFILE_PHOTOS = 'profile-photos';
export const MAX_SOURCE_PHOTO = 30 * 1024 * 1024; // photo choisie : jusqu'à 30 Mo (réduite à ~200 Ko avant l'envoi)

/** Envoie la photo recadrée (JPEG 1024 px, préparée sur le téléphone) dans le dossier du membre ; même format que l'app iOS. */
export async function uploadProfilePhoto(userId: string, uri: string): Promise<string> {
  const blob = await fetch(uri).then((r) => r.blob()).catch(() => null);
  if (!blob) throw new Error('La photo n’a pas pu être lue. Choisis-la à nouveau.');
  if (blob.size > 5 * 1024 * 1024) throw new Error('La photo est trop volumineuse. Choisis-en une autre.');
  const path = `${userId}/${Date.now()}-${Math.random().toString(36).slice(2)}.jpg`;
  const { error } = await supabase.storage.from(PROFILE_PHOTOS).upload(path, blob, { contentType: 'image/jpeg', upsert: false });
  if (error) throw new Error('La photo n’a pas pu être envoyée. Vérifie ta connexion puis réessaie.');
  return path;
}
