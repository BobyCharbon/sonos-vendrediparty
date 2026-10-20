import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Image, View } from 'react-native';

import { Avatar, Button, ErrorText, T } from './ui';

export function ProfilePhotoField({ userId, name, currentPhoto, photo, onChange, disabled }: {
  userId: string;
  name: string;
  currentPhoto: string | null;
  photo: ImagePicker.ImagePickerAsset | null;
  onChange: (photo: ImagePicker.ImagePickerAsset) => void;
  disabled?: boolean;
}) {
  const [error, setError] = useState<string | null>(null);

  async function pick(camera: boolean) {
    setError(null);
    try {
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.7, exif: false, cameraType: ImagePicker.CameraType.front,
      };
      const result = await (camera ? ImagePicker.launchCameraAsync(options) : ImagePicker.launchImageLibraryAsync(options));
      if (!result.canceled && result.assets[0]) {
        const selected = result.assets[0];
        if (selected.fileSize && selected.fileSize > 20 * 1024 * 1024) {
          setError('Cette photo est trop volumineuse. Choisis une image de moins de 20 Mo.');
          return;
        }
        onChange(selected);
      }
    } catch {
      setError('Impossible d’ouvrir les photos. Réessaie ou utilise l’autre option.');
    }
  }

  return (
    <View style={{ gap: 12 }}>
      <T weight="semibold">Photo de profil obligatoire</T>
      <View style={{ alignItems: 'center' }}>
        {photo
          ? <Image accessibilityLabel="Aperçu de ta photo de profil" source={{ uri: photo.uri }} style={{ width: 96, height: 96, borderRadius: 48 }} />
          : <Avatar id={userId} name={name || '?'} photo={currentPhoto} size={96} />}
      </View>
      <T muted size={13}>Choisis une photo pour que le groupe puisse te reconnaître. JPEG, PNG ou WebP, 5 Mo maximum.</T>
      <Button label="Choisir dans la galerie" variant="secondary" disabled={disabled} onPress={() => { void pick(false); }} />
      <Button label="Prendre une photo" variant="secondary" disabled={disabled} onPress={() => { void pick(true); }} />
      <ErrorText error={error} />
    </View>
  );
}
