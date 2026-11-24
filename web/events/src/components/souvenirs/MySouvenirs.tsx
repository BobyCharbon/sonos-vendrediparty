import { useCallback, useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { Avatar, Button, Card, ErrorText, Skeleton, T, Title, Toast } from '@/components/ui';
import { colors, font } from '@/lib/theme';
import {
  deletePhoto, downloadUrl, errorText, fetchMine, nativeSouvenirs, photoWhen, shortDate, unkeepPhoto, type Photo,
} from '@/lib/souvenirs';

type Filter = 'all' | 'me' | 'kept';
const FILM = '#FFB547';

/**
 * « 📸 Mes souvenirs » (maquette v2, écran 7) : mes photos et celles que j'ai gardées pendant la story, dans l'ordre de la
 * soirée, avec leur auteur ; filtre Toutes / Prises par moi / Gardées ; Enregistrer (lien de téléchargement, ou la
 * Photothèque dans l'app iPhone), Supprimer (les miennes, aussi chez ceux qui les avaient gardées) ou Retirer (gardées).
 */
// `hideWhenEmpty` : hors du cercle (passé « Pas présent ») ; la carte ne s'affiche que s'il a encore des photos.
export function MySouvenirs({ eventId, refreshKey, hideWhenEmpty = false }: { eventId: string; refreshKey?: unknown; hideWhenEmpty?: boolean }) {
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [toast, setToast] = useState('');
  const [arm, setArm] = useState<string | null>(null);

  const load = useCallback(() => fetchMine(eventId).then(
    (m) => { setPhotos(m.photos); setError(null); },
    (e: unknown) => setError(errorText(e)),
  ), [eventId]);
  useEffect(() => { void load(); }, [load, refreshKey]);
  useEffect(() => {
    if (!arm) return undefined;
    const t = setTimeout(() => setArm(null), 3000);
    return () => clearTimeout(t);
  }, [arm]);

  if (hideWhenEmpty && !photos?.length) return null;
  if (!photos) return <Card><Title size={18}>📸 Mes souvenirs</Title>{error ? <ErrorText error={error} /> : <Skeleton height={96} />}</Card>;
  const me = photos.filter((p) => p.mine);
  const kept = photos.filter((p) => !p.mine);
  const list = filter === 'me' ? me : filter === 'kept' ? kept : photos;
  const native = nativeSouvenirs();
  const first = photos[0]?.taken_at;
  const ends = first ? new Date(new Date(first).setMonth(new Date(first).getMonth() + 13)).toISOString() : null;

  async function act(p: Photo, kind: 'del' | 'unkeep') {
    setPhotos((all) => (all ?? []).filter((x) => x.id !== p.id));
    try {
      await (kind === 'del' ? deletePhoto(p.id) : unkeepPhoto(p.id));
      setToast(kind === 'del' ? '🗑 Supprimée, aussi chez ceux qui l’avaient gardée' : 'Retirée de tes souvenirs');
    } catch (e) {
      setToast(errorText(e));
      void load();
    }
  }

  const tabs: { key: Filter; label: string; n: number }[] = [
    { key: 'all', label: 'Toutes', n: photos.length }, { key: 'me', label: 'Prises par moi', n: me.length }, { key: 'kept', label: 'Gardées', n: kept.length },
  ];
  return (
    <Card style={{ gap: 12 }}>
      <Title size={18}>📸 Mes souvenirs</Title>
      <View style={st.seg} accessibilityRole="tablist" accessibilityLabel="Filtrer">
        {tabs.map((t) => (
          <Pressable key={t.key} accessibilityRole="tab" accessibilityState={{ selected: filter === t.key }} aria-selected={filter === t.key}
            onPress={() => setFilter(t.key)} style={[st.segBtn, filter === t.key && st.segOn]}>
            <Text style={[st.segText, filter === t.key && { color: colors.text }]}>
              {t.label} <Text style={st.segN}>{t.n}</Text>
            </Text>
          </Pressable>
        ))}
      </View>
      {list.length ? list.map((p) => (
        <View key={p.id} style={st.item} testID="souvenir-item">
          {p.url ? <Image source={{ uri: p.url }} style={st.thumb} accessibilityLabel={`Photo de ${p.mine ? 'toi' : p.author?.name ?? '?'}, ${photoWhen(p.taken_at)}`} />
            : <View style={[st.thumb, { backgroundColor: colors.surface2 }]} />}
          <View style={{ flex: 1, minWidth: 0 }}>
            <T muted size={12}>{photoWhen(p.taken_at)}</T>
            <View style={st.who}>
              {p.author ? <Avatar id={p.author.id} name={p.author.name} photo={p.author.avatar_url} size={22} profile={false} /> : null}
              <T weight="semibold" size={14} numberOfLines={1} style={{ flexShrink: 1 }}>{p.mine ? 'Toi' : p.author?.name ?? '?'}</T>
              <Text style={[st.badge, p.mine && st.badgeMe]}>{p.mine ? '📸 Prise par moi' : '⭐ Gardée'}</Text>
            </View>
          </View>
          <View style={st.acts}>
            {p.url ? (native?.save
              ? <Button small variant="secondary" label="⬇︎ Enregistrer dans la Photothèque" style={{ flex: 1 }} onPress={() => { native.save!(p.original ?? p.url!); }} />
              : <Button small variant="secondary" label="⬇︎ Enregistrer" style={{ flex: 1 }} href={downloadUrl(p.original ?? p.url, `souvenir-${p.taken_at.slice(0, 10)}-${p.id.slice(0, 6)}.jpg`)} />) : null}
            {p.mine ? (
              <Button small variant="danger" label={arm === p.id ? 'Supprimer pour de bon ?' : '🗑 Supprimer'}
                accessibilityLabel={arm === p.id ? 'Supprimer pour de bon ?' : `Supprimer ma photo de ${photoWhen(p.taken_at)}`}
                onPress={() => (arm === p.id ? void act(p, 'del') : setArm(p.id))} />
            ) : (
              <Button small variant="danger" label="Retirer" accessibilityLabel={`Retirer de mes souvenirs la photo de ${p.author?.name ?? '?'}`}
                onPress={() => void act(p, 'unkeep')} />
            )}
          </View>
        </View>
      )) : (
        <T muted size={13} style={{ textAlign: 'center', paddingVertical: 20 }}>
          {filter === 'kept' ? 'Aucune photo gardée. Pendant la story, touche ⭐ sur celles que tu aimes.' : 'Plus aucune photo ici.'}
        </T>
      )}
      <T muted size={12} style={{ lineHeight: 18 }}>
        🔒 Toi seul vois tes souvenirs, dans l’ordre de la soirée. Une photo gardée disparaît si son auteur la supprime, si elle est
        signalée et masquée, ou en cas de blocage.{ends ? ` Effacés le ${shortDate(ends)} (13 mois).` : ' Gardés 13 mois.'}
      </T>
      <ErrorText error={error} />
      {toast ? <Toast message={toast} onHide={() => setToast('')} /> : null}
    </Card>
  );
}

const st = StyleSheet.create({
  seg: { flexDirection: 'row', backgroundColor: colors.bg, borderRadius: 14, padding: 3 },
  segBtn: { flexGrow: 1, flexShrink: 1, flexBasis: 'auto', minHeight: 44, borderRadius: 11, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8 },
  segOn: { backgroundColor: colors.surface2, boxShadow: '0 2px 8px rgba(0,0,0,.3)' } as object,
  segText: { color: colors.muted, fontSize: 13, textAlign: 'center', ...font.semibold },
  segN: { color: colors.accent, fontSize: 12 },
  item: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, backgroundColor: colors.bg, borderRadius: 14, padding: 8 },
  thumb: { width: 72, height: 96, borderRadius: 10 },
  who: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2, flexWrap: 'wrap' },
  badge: { fontSize: 11, ...font.semibold, paddingHorizontal: 7, paddingVertical: 1, borderRadius: 9, backgroundColor: 'rgba(255,181,71,0.18)', color: FILM, overflow: 'hidden' },
  badgeMe: { backgroundColor: 'rgba(255,79,154,0.18)', color: colors.accent },
  acts: { flexDirection: 'row', gap: 6, width: '100%' },
});
