import { useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { C, cf, dateTileFill, Icon, mintButton, web } from './kit';
import type { ChatEventCard } from './data';
import { dateTile, formatTime, plural } from '@/lib/format';
import { pressTransition } from '@/lib/motion';

type Props = {
  card: ChatEventCard | null;
  /** Soirée supprimée ou plus visible : la copie gardée dans le message, sans « Je viens » ni Voir. */
  gone?: boolean;
  /** « Je viens » : réponse Présent (la base décide : liste d'attente, profil, CGU). */
  onYes?: () => Promise<void>;
  onOpen?: () => void;
  /** Aperçu dans la barre de saisie (avant l'envoi) : sans boutons, avec ✕. */
  compact?: boolean;
  onRemove?: () => void;
};

/** Carte d'une soirée Party dans une bulle (maquette 4) : tuile date orange, « SOIRÉE PARTY », titre, heure · lieu,
 * présents, « Je viens » (menthe) et Voir. Soirée que je ne peux pas voir : carte neutre, sans détail. */
export function EventCardBubble({ card, gone = false, onYes, onOpen, compact = false, onRemove }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now] = useState(() => Date.now());
  if (!card) {
    return (
      <View style={[box, { padding: 14 }]}>
        <Text style={[cf.semibold, { color: C.t2, fontSize: 14 }]}>🎉 Soirée indisponible</Text>
        <Text style={[cf.text, { color: C.t3, fontSize: 13, marginTop: 2 }]}>Elle a été retirée, ou tu n’y as pas accès.</Text>
      </View>
    );
  }
  const tile = card.start ? dateTile(card.start) : null;
  const past = card.start ? Date.parse(card.start) < now - 6 * 3600_000 : false;
  const line = [card.start ? formatTime(card.start).replace(':', ' h ') : 'Date à définir', card.place].filter(Boolean).join(' · ');
  const going = card.mine === 'yes';
  const open = gone ? undefined : onOpen;

  async function yes() {
    if (!onYes || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onYes();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ta réponse n’a pas pu être enregistrée.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[box, compact && { width: '100%', maxWidth: 360 }]}>
      <View style={[{ position: 'absolute', left: 0, right: 0, top: 0, height: 3 }, web({ backgroundImage: 'linear-gradient(90deg, #FFC977, #FF7A59, #FF4F9A)' })]} />
      <Pressable accessibilityRole={open ? 'link' : undefined} accessibilityLabel={`Soirée ${card.title}${tile ? `, ${tile.weekday} ${tile.day}` : ''}${open ? '. Voir la fiche' : ''}`}
        onPress={open} disabled={!open} style={({ pressed }) => [{ flexDirection: 'row', gap: 12, alignItems: 'center' }, pressTransition, pressed && { opacity: 0.8 }]}>
        <View style={[{ width: 50, height: 50, borderRadius: 15, alignItems: 'center', justifyContent: 'center' }, dateTileFill]}>
          {tile ? (
            <>
              <Text style={[cf.label, { fontSize: 10, lineHeight: 12, color: '#2A1406', opacity: 0.82 }]}>{tile.weekday}</Text>
              <Text style={[cf.display, { fontSize: 22, lineHeight: 22, color: '#2A1406' }]}>{tile.day}</Text>
            </>
          ) : <Text style={{ fontSize: 22 }}>🗓️</Text>}
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
            <Icon name="sparkle" size={13} color={C.coral} stroke={2.4} />
            <Text style={[cf.label, { color: C.coral }]}>Soirée Party</Text>
          </View>
          <Text numberOfLines={1} style={[cf.display, { color: C.t1, fontSize: 18, lineHeight: 22, marginTop: 1 }]}>{card.title}</Text>
          <Text numberOfLines={1} style={[cf.text, { color: C.t2, fontSize: 14, lineHeight: 19 }]}>{line}</Text>
        </View>
        {compact && onRemove ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Retirer la soirée du message" onPress={onRemove} hitSlop={6}
            style={{ width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: C.glass }}>
            <Icon name="x" size={16} color={C.t2} stroke={2.2} />
          </Pressable>
        ) : null}
      </Pressable>
      {gone ? (
        <Text style={[cf.text, { color: C.t3, fontSize: 13, marginTop: 10 }]}>Cette soirée a été retirée.</Text>
      ) : compact ? null : (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12 }}>
          <Text style={[cf.text, { flex: 1, color: C.t2, fontSize: 13 }]}>{plural(card.going, 'présent')}</Text>
          {going ? (
            <View accessibilityLabel="Tu viens" style={{ height: 40, paddingHorizontal: 12, borderRadius: 20, flexDirection: 'row', alignItems: 'center', gap: 6,
              backgroundColor: 'rgba(91,227,166,0.14)', borderWidth: 1, borderColor: 'rgba(91,227,166,0.4)' }}>
              <Icon name="check" size={16} color={C.mint} stroke={2.4} />
              <Text style={[cf.bold, { color: C.mint, fontSize: 15 }]}>Tu viens</Text>
            </View>
          ) : onYes && !past ? (
            <Pressable accessibilityRole="button" accessibilityLabel="Répondre : je viens" accessibilityState={{ busy }} onPress={() => void yes()}
              style={({ pressed }) => [{ height: 40, paddingHorizontal: 14, borderRadius: 20, flexDirection: 'row', alignItems: 'center', gap: 6 },
                mintButton, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
              {busy ? <ActivityIndicator size="small" color={C.onMint} /> : <Icon name="check" size={16} color={C.onMint} stroke={2.4} />}
              <Text style={[cf.bold, { color: C.onMint, fontSize: 15 }]}>Je viens</Text>
            </Pressable>
          ) : null}
          <Pressable accessibilityRole="button" accessibilityLabel={`Voir la soirée ${card.title}`} onPress={open}
            style={({ pressed }) => [{ height: 40, minWidth: 44, paddingHorizontal: 14, borderRadius: 20, alignItems: 'center', justifyContent: 'center',
              backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine }, pressTransition, pressed && { opacity: 0.7 }]}>
            <Text style={[cf.bold, { color: C.t1, fontSize: 15 }]}>Voir</Text>
          </Pressable>
        </View>
      )}
      {error ? <Text accessibilityRole="alert" style={[cf.text, { color: C.danger, fontSize: 13, marginTop: 8 }]}>{error}</Text> : null}
    </View>
  );
}

const box = [{ width: 300, maxWidth: '100%' as const, borderRadius: 22, overflow: 'hidden' as const, padding: 12, borderWidth: 1, borderColor: 'rgba(255,179,71,0.22)' },
  web({ backgroundColor: C.theirs, backgroundImage: 'radial-gradient(120% 80% at 0% 0%, rgba(255,122,89,0.22), transparent 60%)',
    boxShadow: '0 14px 30px -18px rgba(255,122,89,0.55)' })];
