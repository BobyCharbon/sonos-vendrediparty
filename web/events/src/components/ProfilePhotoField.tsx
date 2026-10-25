import { useRef, useState } from 'react';
import { Image, View } from 'react-native';

import { MAX_SOURCE_PHOTO } from '@/lib/photos';
import { PhotoCropper } from './PhotoCropper';
import { Avatar, Button, ErrorText, T } from './ui';

/** Photo de profil : galerie ou appareil photo, tous formats que le téléphone sait lire, puis recadrage libre. */
export function ProfilePhotoField({ userId, name, currentPhoto, photo, onChange, disabled }: {
  userId: string;
  name: string;
  currentPhoto: string | null;
  photo: string | null; // photo recadrée, pas encore envoyée
  onChange: (uri: string) => void;
  disabled?: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);

  function picked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // rechoisir la même photo rouvre le recadrage
    if (!file) return;
    setError(null);
    if (file.type && !file.type.startsWith('image/')) return setError('Choisis une image (photo, capture d’écran…).');
    if (file.size > MAX_SOURCE_PHOTO) return setError('Cette photo dépasse 30 Mo. Choisis-en une plus légère.');
    setSource(URL.createObjectURL(file));
  }

  return (
    <View style={{ gap: 12 }}>
      <T weight="semibold">Photo de profil (obligatoire)</T>
      <View style={{ alignItems: 'center' }}>
        {photo
          ? <Image accessibilityLabel="Aperçu de ta photo de profil" source={{ uri: photo }} style={{ width: 96, height: 96, borderRadius: 48 }} />
          : <Avatar id={userId} name={name || '?'} photo={currentPhoto} size={96} />}
      </View>
      <T muted size={13}>Pour que le groupe te reconnaisse, dans les jeux comme dans les événements. Tu la recadres juste après l’avoir choisie.</T>
      <input ref={gallery} type="file" accept="image/*,.heic,.heif" hidden onChange={picked} />
      <input ref={camera} type="file" accept="image/*" capture="user" hidden onChange={picked} />
      <Button label={photo || currentPhoto ? 'Changer de photo' : 'Choisir une photo'} variant="secondary" disabled={disabled} onPress={() => gallery.current?.click()} />
      <Button label="Prendre une photo" variant="secondary" disabled={disabled} onPress={() => camera.current?.click()} />
      <ErrorText error={error} />
      {source ? (
        <PhotoCropper
          src={source}
          onCancel={() => { URL.revokeObjectURL(source); setSource(null); }}
          onDone={(uri) => { URL.revokeObjectURL(source); setSource(null); onChange(uri); }}
        />
      ) : null}
    </View>
  );
}
