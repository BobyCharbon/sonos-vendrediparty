import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { ActivityIndicator, Image, Modal, PanResponder, Pressable, StyleSheet, Text, View } from 'react-native';

import { SheetClose, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { signedPhotoUrl } from '@/components/ui';
import { useMaySeePhoto } from '@/lib/auth';
import { duration, ease, enter, transition } from '@/lib/motion';

/**
 * Photo de profil en grand (avis 163be6ce5df6, 20.11) : toucher la photo d'un profil l'ouvre en plein écran dans sa
 * qualité réelle (le fichier enregistré, 1024 px, jamais une miniature). Toucher deux fois pour zoomer, glisser vers le
 * bas, ✕ ou le fond pour fermer.
 */
export function PhotoTap({ photo, name, children }: { photo: string | null | undefined; name: string; children: ReactNode }) {
  const maySee = useMaySeePhoto();
  const [open, setOpen] = useState(false);
  const visible = !!photo && (/^https?:/.test(photo) || maySee(photo));
  if (!visible) return <>{children}</>;
  return (
    <>
      <Pressable accessibilityRole="button" accessibilityLabel={`Voir la photo de ${name} en grand`} testID="profile-photo-open"
        onPress={() => setOpen(true)} style={({ pressed }) => [pressed && { opacity: 0.85, transform: [{ scale: 0.97 }] }, transition('transform, opacity', duration.fast)]}>
        {children}
      </Pressable>
      {open ? <ProfilePhotoViewer photo={photo!} name={name} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function ProfilePhotoViewer({ photo, name, onClose }: { photo: string; name: string; onClose: () => void }) {
  const direct = /^https?:/.test(photo);
  const [signed, setSigned] = useState<string | null | undefined>(undefined);
  const url = direct ? photo : signed;
  const [zoom, setZoom] = useState(false);
  const [drag, setDrag] = useState(0);
  const [failed, setFailed] = useState(false);
  const [lastTap, setLastTap] = useState(0);
  const top = useSheetTop();
  useSheetSignal(true);  // la pastille de Zicou ne couvre pas le ✕

  useEffect(() => {
    if (direct) return undefined;
    let live = true;
    void signedPhotoUrl(photo).then((u) => { if (live) setSigned(u); });
    return () => { live = false; };
  }, [photo, direct]);

  // Glisser vers le bas (sans zoom) ferme ; la photo suit le doigt.
  const pan = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_e, g) => !zoom && Math.abs(g.dy) > 10 && Math.abs(g.dy) > Math.abs(g.dx),
    onPanResponderMove: (_e, g) => setDrag(Math.max(0, g.dy)),
    onPanResponderRelease: (_e, g) => { setDrag(0); if (g.dy > 110 || g.vy > 0.8) onClose(); },
    onPanResponderTerminate: () => setDrag(0),
  }), [zoom, onClose]);

  const tap = (e: { timeStamp: number }) => {
    if (e.timeStamp - lastTap < 320) { setZoom((z) => !z); setLastTap(0); } else setLastTap(e.timeStamp);
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={[st.screen, { backgroundColor: `rgba(0,0,0,${Math.max(0.45, 1 - drag / 500)})` }]} testID="profile-photo-full"
        accessibilityViewIsModal accessibilityLabel={`Photo de profil de ${name}`}>
        <Pressable accessibilityLabel="Fermer la photo" onPress={onClose} style={StyleSheet.absoluteFill} />
        {url ? (
          <View {...pan.panHandlers} style={[st.frame, { transform: [{ translateY: drag }] }, drag ? null : transition('transform', duration.base, ease.out)]}>
            <Pressable accessibilityRole="image" accessibilityLabel={`Photo de ${name}${zoom ? ', agrandie' : ''}. Toucher deux fois pour zoomer.`}
              onPress={tap} style={st.frame}>
              <View style={[st.frame, { transform: [{ scale: zoom ? 2.2 : 1 }] }, transition('transform', duration.base, ease.out), enter('pop')]}>
                <Image source={{ uri: url }} resizeMode="contain" onError={() => setFailed(true)} style={st.image} />
              </View>
            </Pressable>
          </View>
        ) : signed === null || failed ? (
          <Text style={st.error}>La photo n’a pas pu s’afficher.</Text>
        ) : (
          <ActivityIndicator color="#fff" />
        )}
        {failed && url ? <Text style={[st.error, { position: 'absolute', bottom: 60 }]}>La photo n’a pas pu s’afficher.</Text> : null}
        <SheetClose onPress={onClose} label="Fermer" style={[st.close, { top }]} />
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  frame: { width: '100%', height: '100%', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  image: { width: '100%', height: '100%', maxWidth: 1024, maxHeight: 1024 },
  close: { position: 'absolute', left: 16, backgroundColor: 'rgba(255,255,255,0.16)' },
  error: { color: 'rgba(255,255,255,0.8)', fontSize: 15 },
});
