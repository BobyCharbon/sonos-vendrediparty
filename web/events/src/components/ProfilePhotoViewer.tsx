import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { ActivityIndicator, Image, Modal, PanResponder, Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';

import { SheetClose, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { signedPhotoUrl } from '@/components/ui';
import { useMaySeePhoto } from '@/lib/auth';
import { duration, ease, enter, transition } from '@/lib/motion';

/**
 * Photo de profil en grand (avis 163be6ce5df6, 20.11) : toucher la photo d'un profil l'ouvre en plein écran dans sa
 * qualité réelle (le fichier enregistré, 1024 px, jamais une miniature). Toucher deux fois pour zoomer (puis glisser pour
 * se déplacer), glisser vers le bas, ✕ ou toucher hors de la photo pour fermer.
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
  // Photo agrandie : déplacée au doigt.
  const [shift, setShift] = useState({ x: 0, y: 0 });
  const [failed, setFailed] = useState(false);
  const [lastTap, setLastTap] = useState(0);
  // Taille réelle de la photo : la zone touchable est la photo seule, le fond autour ferme.
  const [ratio, setRatio] = useState(1);
  const { width, height } = useWindowDimensions();
  const top = useSheetTop();
  useSheetSignal(true);  // la pastille de Zicou ne couvre pas le ✕

  useEffect(() => {
    if (direct) return undefined;
    let live = true;
    void signedPhotoUrl(photo).then((u) => { if (live) setSigned(u); });
    return () => { live = false; };
  }, [photo, direct]);

  useEffect(() => {
    if (!url) return;
    Image.getSize(url, (w, h) => { if (w > 0 && h > 0) setRatio(w / h); }, () => {});
  }, [url]);

  const boxW = Math.min(width, height * ratio, 1024);
  const boxH = boxW / ratio;
  const Z = 2.2;
  const limit = { x: (boxW * Z - boxW) / 2, y: Math.max(0, (boxH * Z - height) / 2 + boxH * 0.1) };
  const clamp = (v: number, m: number) => Math.max(-m, Math.min(m, v));

  // Sans zoom : glisser vers le bas ferme. Agrandie : glisser déplace la photo.
  // Le geste en cours n'est jamais recréé (dépendances stables pendant le glissé) : on avance du chemin fait depuis le
  // dernier mouvement (gardé sur le geste lui-même).
  const pan = useMemo(() => {
    type G = { dx: number; dy: number; px?: number; py?: number };
    return PanResponder.create({
      onMoveShouldSetPanResponder: (_e, g) => (zoom ? Math.abs(g.dx) + Math.abs(g.dy) > 6 : Math.abs(g.dy) > 10 && Math.abs(g.dy) > Math.abs(g.dx)),
      onPanResponderMove: (_e, gs) => {
        const g = gs as unknown as G;
        if (!zoom) return setDrag(Math.max(0, g.dy));
        const mx = g.dx - (g.px ?? 0), my = g.dy - (g.py ?? 0);
        g.px = g.dx;
        g.py = g.dy;
        setShift((s) => ({ x: clamp(s.x + mx, limit.x), y: clamp(s.y + my, limit.y) }));
      },
      onPanResponderRelease: (_e, g) => {
        if (zoom) return;
        setDrag(0);
        if (g.dy > 110 || g.vy > 0.8) onClose();
      },
      onPanResponderTerminate: () => setDrag(0),
    });
  }, [zoom, onClose, limit.x, limit.y]);

  const tap = (e: { timeStamp: number }) => {
    if (e.timeStamp - lastTap < 320) {
      setZoom((z) => !z);
      setShift({ x: 0, y: 0 });
      setLastTap(0);
    } else setLastTap(e.timeStamp);
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={[st.screen, { backgroundColor: `rgba(0,0,0,${Math.max(0.45, 1 - drag / 500)})` }]} testID="profile-photo-full"
        accessibilityViewIsModal accessibilityLabel={`Photo de profil de ${name}`}>
        {/* Autour de la photo : ferme ; agrandie, la photo déborde : le toucher la remet à sa taille. */}
        <Pressable accessibilityLabel={zoom ? 'Réduire la photo' : 'Fermer la photo'} testID="profile-photo-backdrop" style={StyleSheet.absoluteFill}
          onPress={() => { if (!zoom) return onClose(); setZoom(false); setShift({ x: 0, y: 0 }); }} />
        {url ? (
          <View {...pan.panHandlers} style={[{ width: boxW, height: boxH }, { transform: [{ translateY: drag }] },
            drag ? null : transition('transform', duration.base, ease.out)]}>
            <Pressable accessibilityRole="image" accessibilityLabel={`Photo de ${name}${zoom ? ', agrandie' : ''}. Toucher deux fois pour zoomer.`}
              onPress={tap} style={{ width: boxW, height: boxH }}>
              <View style={[{ width: boxW, height: boxH }, { transform: [{ translateX: shift.x }, { translateY: shift.y }, { scale: zoom ? Z : 1 }] },
                transition('transform', duration.base, ease.out), enter('pop')]}>
                <Image source={{ uri: url }} resizeMode="contain" onError={() => setFailed(true)} style={{ width: boxW, height: boxH }} />
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
  close: { position: 'absolute', left: 16, backgroundColor: 'rgba(255,255,255,0.16)' },
  error: { color: 'rgba(255,255,255,0.8)', fontSize: 15 },
});
