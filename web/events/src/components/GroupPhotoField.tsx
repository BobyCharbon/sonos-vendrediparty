import { useRef, useState } from 'react';
import { View } from 'react-native';

import { MAX_SOURCE_PHOTO } from '@/lib/photos';
import { PhotoCropper } from './PhotoCropper';
import { Button, ConfirmButton, ErrorText, T } from './ui';

/** Photo du groupe (facultative) : galerie ou appareil photo, recadrage carré, puis onPicked ; « Retirer » si elle existe. */
export function GroupPhotoField({ has, disabled, onPicked, onRemove }: {
  has: boolean;
  disabled?: boolean;
  onPicked: (uri: string) => void;
  onRemove?: () => void;
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
    <View style={{ gap: 8 }} testID="group-photo-field">
      <T size={14} weight="semibold">Photo du groupe (facultative)</T>
      <T muted size={13}>Elle remplace l’emoji et devient la couverture du groupe. Seuls ses membres la voient, et ils peuvent la signaler.</T>
      <input ref={gallery} type="file" accept="image/*,.heic,.heif" hidden onChange={picked} data-testid="group-photo-input" />
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={picked} />
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        <Button small variant="secondary" label={has ? '🖼️  Changer la photo' : '🖼️  Choisir une photo'} disabled={disabled}
          onPress={() => gallery.current?.click()} />
        <Button small variant="secondary" label="📷  Prendre une photo" disabled={disabled} onPress={() => camera.current?.click()} />
        {has && onRemove ? <ConfirmButton small label="Retirer la photo" confirmLabel="Confirmer" onConfirm={onRemove} /> : null}
      </View>
      <ErrorText error={error} />
      {source ? (
        <PhotoCropper
          src={source}
          label="Recadrer la photo du groupe"
          onCancel={() => { URL.revokeObjectURL(source); setSource(null); }}
          onDone={(uri) => { URL.revokeObjectURL(source); setSource(null); onPicked(uri); }}
        />
      ) : null}
    </View>
  );
}
