import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import { colors, radius } from '@/lib/theme';

import { Input, T } from './ui';

/** Clé publique Google (limitée aux domaines de Party dans Google Cloud) ; sans elle, pas de recherche. */
const KEY = process.env.EXPO_PUBLIC_GOOGLE_MAPS_KEY;
const API = 'https://places.googleapis.com/v1';

type Suggestion = { id: string; main: string; secondary: string };
export type Place = { name: string; address: string; url: string };

/** Recherche Google Maps : choisir un lieu remplit nom, adresse et lien Google Maps. */
export function PlaceSearch({ onPick }: { onPick: (place: Place) => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Suggestion[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Une session Google = une recherche jusqu’au choix (facturée comme une seule).
  const [session, setSession] = useState(newSession);

  useEffect(() => {
    if (!KEY || query.trim().length < 3) return;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/places:autocomplete`, {
          method: 'POST',
          signal: ctrl.signal,
          headers: { 'Content-Type': 'application/json', 'X-Goog-Api-Key': KEY },
          body: JSON.stringify({ input: query.trim(), languageCode: 'fr', regionCode: 'ch', sessionToken: session }),
        });
        if (!res.ok) throw new Error();
        const body = (await res.json()) as { suggestions?: { placePrediction?: { placeId: string; structuredFormat?: { mainText?: { text: string }; secondaryText?: { text: string } } } }[] };
        setResults((body.suggestions ?? []).flatMap(({ placePrediction: p }) =>
          p ? [{ id: p.placeId, main: p.structuredFormat?.mainText?.text ?? '', secondary: p.structuredFormat?.secondaryText?.text ?? '' }] : []));
        setError(null);
      } catch {
        if (!ctrl.signal.aborted) setError('La recherche Google Maps ne répond pas. Tu peux remplir le lieu à la main.');
      }
    }, 300);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [query, session]);

  if (!KEY) return null;

  async function pick(s: Suggestion) {
    try {
      const res = await fetch(`${API}/places/${encodeURIComponent(s.id)}?languageCode=fr&sessionToken=${session}`, {
        headers: { 'X-Goog-Api-Key': KEY!, 'X-Goog-FieldMask': 'displayName,formattedAddress,googleMapsUri' },
      });
      if (!res.ok) throw new Error();
      const p = (await res.json()) as { displayName?: { text: string }; formattedAddress?: string; googleMapsUri?: string };
      onPick({ name: p.displayName?.text ?? s.main, address: p.formattedAddress ?? s.secondary, url: p.googleMapsUri ?? '' });
      setQuery('');
      setResults([]);
      setSession(newSession());
    } catch {
      setError('Impossible de récupérer ce lieu. Réessaie ou remplis-le à la main.');
    }
  }

  const shown = query.trim().length >= 3 ? results : [];
  return (
    <View style={{ gap: 6 }}>
      <T muted size={13}>Chercher sur Google Maps</T>
      <Input accessibilityLabel="Chercher un lieu sur Google Maps" placeholder="Bar, resto, adresse…" value={query} onChangeText={setQuery} autoCorrect={false} />
      {shown.length ? (
        <View role="list" style={{ borderWidth: 1, borderColor: colors.lineStrong, borderRadius: radius.md, overflow: 'hidden' }}>
          {shown.map((s, i) => (
            <Pressable
              key={s.id}
              role="button"
              accessibilityLabel={`${s.main}, ${s.secondary}`}
              onPress={() => pick(s)}
              style={({ pressed }) => ({ minHeight: 48, paddingHorizontal: 12, paddingVertical: 8, justifyContent: 'center', backgroundColor: pressed ? colors.surface2 : colors.bg, borderTopWidth: i ? 1 : 0, borderTopColor: colors.line })}
            >
              <T weight="semibold" size={14} numberOfLines={1}>{s.main}</T>
              {s.secondary ? <T muted size={12} numberOfLines={1}>{s.secondary}</T> : null}
            </Pressable>
          ))}
        </View>
      ) : null}
      {error ? <T size={12} color={colors.coral}>{error}</T> : null}
    </View>
  );
}

function newSession() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
