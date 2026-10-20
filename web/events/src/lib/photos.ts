import type { ImagePickerAsset } from 'expo-image-picker';

import { supabase } from './supabase';

export const PROFILE_PHOTOS = 'profile-photos';

async function prepareBrowserPhoto(photo: ImagePickerAsset): Promise<ArrayBuffer> {
  // Le réencodage retire les métadonnées et limite le poids des portraits.
  const image = new Image();
  image.src = photo.uri;
  await image.decode().catch(() => { throw new Error('Cette photo ne peut pas être lue. Choisis une image JPEG, PNG ou WebP.'); });
  const scale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('La photo ne peut pas être préparée. Réessaie avec une autre image.');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.8));
  if (!blob) throw new Error('La photo ne peut pas être préparée. Réessaie avec une autre image.');
  return blob.arrayBuffer();
}

/** Envoie la photo (module web uniquement) dans le dossier du membre ; même format que l'app iOS. */
export async function uploadProfilePhoto(userId: string, photo: ImagePickerAsset): Promise<string> {
  const bytes = await prepareBrowserPhoto(photo);
  if (bytes.byteLength > 5 * 1024 * 1024) throw new Error('La photo est trop volumineuse. Choisis une image de moins de 5 Mo.');
  const path = `${userId}/${Date.now()}-${Math.random().toString(36).slice(2)}.jpg`;
  const { error } = await supabase.storage.from(PROFILE_PHOTOS).upload(path, bytes, { contentType: 'image/jpeg', upsert: false });
  if (error) throw new Error('La photo n’a pas pu être envoyée. Vérifie ta connexion puis réessaie.');
  return path;
}
