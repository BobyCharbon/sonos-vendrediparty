import { Pressable, StyleSheet, Text, View } from 'react-native';

import { CoverBand, Countdown, GlassCard, KindIcon, kindLabel } from '@/components/pronos/Kit';
import { gradient } from '@/lib/groups';
import { pointsLabel } from '@/lib/pronos';
import { pressTransition } from '@/lib/motion';

import { C, rounded, webView, withPatates, type PronoV2 } from './model';

/**
 * En-tête de la fiche (maquette 3-1) : couverture du groupe ou de l'événement (boutons ronds en verre par-dessus),
 * tuile du groupe + « prono de Ludo », la question, les étiquettes (type, avec patates, points), « Comment on
 * tranche ? » et le compte à rebours (3 paliers, Kit). Les étiquettes ne sont pas des boutons.
 */
export function Header({ p, compact, onBack, onShare, onMore }: {
  p: PronoV2; compact: boolean; onBack: () => void; onShare?: () => void; onMore?: () => void;
}) {
  const patates = withPatates(p);
  const tags: { key: string; icon?: boolean; label: string; tone?: 'patate' }[] = [{ key: 'kind', icon: true, label: kindLabel(p.kind) }];
  if (p.not_over) tags.push({ key: 'not_over', label: '↓ Sans dépasser' });
  if (patates) tags.push({ key: 'patates', label: '🥔 Avec patates', tone: 'patate' });
  if (p.kind !== 'award') tags.push({ key: 'points', label: patates ? pointsLabel(p.points) : `${pointsLabel(p.points)}, pour l’honneur` });
  if (p.mine && p.state === 'open') tags.push({ key: 'played', label: `${p.answered.length} ${p.answered.length > 1 ? 'ont joué' : 'a joué'}` });
  const place = p.group ? p.group.name : p.event ? p.event.title : null;
  return (
    <View>
      <View style={{ marginHorizontal: -16, marginTop: -16 }}>
        <CoverBand group={p.group} event={p.event} height={compact ? 200 : 236} />
        <View style={st.bar}>
          <Round label="Retour" glyph="‹" onPress={onBack} />
          <View style={{ flexDirection: 'row', gap: 10 }}>
            {onShare ? <Round label="Partager le lien du prono" glyph="⇪" onPress={onShare} /> : null}
            {onMore ? <Round label="Plus d’actions" glyph="•••" onPress={onMore} /> : null}
          </View>
        </View>
      </View>
      <View style={[st.body, { marginTop: compact ? -56 : -72 }]}>
        <View style={st.placeRow}>
          {p.group ? (
            <View style={[st.tile, gradient(p.group.color)]}><Text style={{ fontSize: 18 }}>{p.group.emoji}</Text></View>
          ) : p.event ? <View style={[st.tile, { backgroundColor: 'rgba(185,167,255,0.2)' }]}><Text style={{ fontSize: 18 }}>📅</Text></View> : null}
          {place ? <Text style={st.place} numberOfLines={1}>{place}</Text> : null}
          <Text style={st.by} numberOfLines={1}>{p.mine ? 'ton prono' : `prono de ${p.creator.name}`}</Text>
        </View>
        <Text role="heading" aria-level={1} style={st.question}>{p.question}</Text>
        <View style={st.tags}>
          {tags.map((t) => (
            <View key={t.key} style={[st.tag, t.tone === 'patate' && st.tagPatate]}>
              {t.icon ? <KindIcon kind={p.kind} /> : null}
              <Text style={[st.tagText, t.tone === 'patate' && { color: C.patate }]}>{t.label}</Text>
            </View>
          ))}
        </View>
        {p.rules ? (
          <GlassCard style={st.rules}>
            <View style={st.rulesIcon}><Text style={{ fontSize: 17 }} accessibilityElementsHidden>⚖️</Text></View>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={rounded(16, '700')}>Comment on tranche ?</Text>
              <Text style={st.help}>{p.rules}</Text>
            </View>
          </GlassCard>
        ) : null}
        {p.state === 'open' ? <Countdown closesAt={p.closes_at} /> : null}
      </View>
    </View>
  );
}

function Round({ label, glyph, onPress }: { label: string; glyph: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [st.round, pressTransition, pressed && { transform: [{ scale: 0.94 }] }]}>
      <Text style={{ color: C.t1, fontSize: glyph === '‹' ? 26 : 15, fontWeight: '700', marginTop: glyph === '‹' ? -3 : 0 }}>{glyph}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  bar: { position: 'absolute', top: 12, left: 16, right: 16, flexDirection: 'row', justifyContent: 'space-between' },
  round: webView({ width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(14,10,31,0.45)', borderWidth: 1, borderColor: C.glassLine, backdropFilter: 'blur(20px)' }),
  body: { gap: 14 },
  placeRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  tile: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  place: { color: C.t1, fontSize: 15, fontWeight: '700', flexShrink: 1 },
  by: { color: C.t2, fontSize: 15, flexShrink: 1 },
  question: webView({ ...rounded(30), lineHeight: 34, letterSpacing: -0.3, textWrap: 'balance' }) as object,
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 28, paddingHorizontal: 11, borderRadius: 999,
    backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine },
  tagPatate: { backgroundColor: 'rgba(245,194,122,0.10)', borderColor: 'rgba(245,194,122,0.45)' },
  tagText: { color: C.t1, fontSize: 13, fontWeight: '600' },
  rules: { flexDirection: 'row', gap: 12, padding: 16, borderRadius: 20 },
  rulesIcon: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(185,167,255,0.16)' },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
});
