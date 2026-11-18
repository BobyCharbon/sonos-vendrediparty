import { StyleSheet, Text, View } from 'react-native';

import { AvatarStack, ChoicePill, Countdown, CoverBand, KindIcon, kindLabel, PatateBadge } from '@/components/pronos/Kit';
import { palette } from '@/lib/groups';
import type { Face } from '@/lib/pronos';

import { awardOf, filledOptions, lineLabel, shownQuestion, type Award, type Draft } from './model';
import { C, nb, rounded, Txt, web } from './ui';

export type Place = {
  group: { id: string; name: string; emoji: string; color: string; photo: string | null } | null;
  event: { id: string; title: string } | null;
  /** Nom court affiché sur la couverture (« Les Grenats », « Anniv de Léa », « Invités »). */
  label: string; emoji: string; faces: Face[]; members: number;
};


/**
 * Aperçu en direct (maquettes 2-2 et 2-4) : la carte telle que la bande la verra dans sa liste, mise à jour à chaque
 * frappe. Rien n'y est touchable : c'est une image de la carte (VoiceOver la lit en une phrase).
 */
export function PreviewCard({ d, awards, place, closesAt, patates, launched }: {
  d: Draft; awards: Award[]; place: Place; closesAt?: string | null; patates?: boolean; launched?: boolean;
}) {
  const color = palette(place.group?.color ?? (place.event ? 'coral' : 'lavender'));
  const q = shownQuestion(d, awards);
  const award = d.kind === 'award' ? awardOf(d, awards) : null;
  return (
    <View accessible accessibilityLabel={`Aperçu de la carte : ${q || 'ta question'}, ${kindLabel(d.kind)}`}
      style={[st.card, web({ boxShadow: `0 18px 60px ${color.main}55`, pointerEvents: 'none' })]} testID="prono-preview">
      <View>
        <CoverBand group={place.group} event={place.event} height={74} />
        <View style={st.coverRow}>
          <View style={st.placeChip}>
            <Text style={{ fontSize: 15 }}>{place.emoji}</Text>
            <Txt size={15} weight="700" color="#fff" numberOfLines={1} style={{ maxWidth: 170 }}>{place.label}</Txt>
          </View>
          <View style={st.kindChip}>
            <KindIcon kind={d.kind} />
            <Txt size={15} weight="700" color="#1D1530">{kindLabel(d.kind)}</Txt>
          </View>
        </View>
      </View>
      <View style={st.body}>
        {award ? (
          <Text style={[rounded, st.q, { color: C.lemon }]}>{award.emoji} {award.label}</Text>
        ) : (
          <Text style={[rounded, st.q, !q && { color: C.t3 }]} numberOfLines={4}>{q ? nb(q) : 'Ta question s’écrit ici'}</Text>
        )}
        <Answers d={d} place={place} />
        <View style={st.foot}>
          <View style={st.seals}>
            {[0, 1, 2].map((i) => <View key={i} style={[st.dash, i > 0 && { marginLeft: -12 }]} />)}
          </View>
          <Txt size={14} color={C.t2} style={{ flex: 1 }} numberOfLines={1}>{launched ? 'Personne n’a encore joué' : 'À toi de lancer'}</Txt>
          {!launched ? (
            <View style={st.endChip}><Txt size={14} color={C.t2} weight="600">🕒 {closesAt ? 'fin choisie' : 'fin à choisir'}</Txt></View>
          ) : null}
        </View>
        {launched ? (
          <View style={[st.foot, { justifyContent: 'space-between' }]}>
            {patates ? (
              <View style={st.field}><PatateBadge n={0} tone="potato" /><Txt size={14} weight="700" color={C.amber}>sur la piste</Txt></View>
            ) : <View />}
            {closesAt ? <Countdown closesAt={closesAt} /> : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}

function Answers({ d, place }: { d: Draft; place: Place }) {
  if (d.kind === 'choice' || d.kind === 'majority') {
    const opts = filledOptions(d);
    if (!opts.length) return <Txt size={14} color={C.t3}>Tes réponses s’afficheront ici.</Txt>;
    return (
      <View style={st.pills}>
        {opts.map((o, i) => <ChoicePill key={`${i}-${o}`} label={o} shape={i} />)}
      </View>
    );
  }
  if (d.kind === 'yesno') {
    return (
      <View style={st.pills}>
        <ChoicePill label="Oui" shape={0} />
        <ChoicePill label="Non" shape={1} />
      </View>
    );
  }
  if (d.kind === 'overunder') {
    return (
      <View style={st.pills}>
        <ChoicePill label={`Plus de ${lineLabel(d.line)}`} shape="triangle" />
        <ChoicePill label={`Moins de ${lineLabel(d.line)}`} shape="down" />
      </View>
    );
  }
  if (d.kind === 'number' || d.kind === 'when') {
    return (
      <View style={st.line}>
        <Text style={{ fontSize: 20 }}>{d.kind === 'number' ? '🎯' : '⏰'}</Text>
        <Txt size={15} color={C.t2} style={{ flex: 1 }}>
          {d.kind === 'number' ? 'Le nombre le plus proche l’emporte' : 'L’heure la plus proche l’emporte'}
          {d.notOver ? ', sans dépasser' : ''}
        </Txt>
      </View>
    );
  }
  if (d.kind === 'person' || d.kind === 'award') {
    const extra = Math.max(0, place.members - place.faces.length);
    return (
      <View style={{ gap: 10 }}>
        <View style={st.line}>
          {place.faces.length ? <AvatarStack faces={place.faces.slice(0, 4)} extra={extra + Math.max(0, place.faces.length - 4)} /> : null}
          <Txt size={15} color={C.t2} style={{ flex: 1, textAlign: place.faces.length ? 'right' : 'left' }}>
            {d.kind === 'award' ? 'Vote pour quelqu’un' : 'Choisis quelqu’un de la bande'}
          </Txt>
        </View>
        {d.kind === 'award' ? (
          <View style={st.pills}>
            <View style={st.tag}><Txt size={14} weight="600">🏅 Pour l’honneur</Txt></View>
            <View style={st.tag}><Txt size={14} weight="600">3 votes au moins</Txt></View>
          </View>
        ) : null}
      </View>
    );
  }
  return (
    <View style={st.line}>
      <Text style={{ fontSize: 20 }}>✍️</Text>
      <Txt size={15} color={C.t2}>Chacun écrit sa réponse</Txt>
    </View>
  );
}

const st = StyleSheet.create({
  card: { borderRadius: 24, overflow: 'hidden', backgroundColor: C.s1, borderWidth: 1, borderColor: C.lineStrong },
  coverRow: { position: 'absolute', top: 12, left: 12, right: 12, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  placeChip: web({ flexDirection: 'row', alignItems: 'center', gap: 6, height: 34, paddingHorizontal: 12, borderRadius: 17,
    backgroundColor: 'rgba(40,24,30,0.45)', backdropFilter: 'blur(12px)', flexShrink: 1 }),
  kindChip: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 34, paddingHorizontal: 12, borderRadius: 17, backgroundColor: '#FFFFFF' },
  body: { padding: 18, gap: 14 },
  q: { fontSize: 26, lineHeight: 29, color: C.t1 },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  line: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  foot: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  seals: { flexDirection: 'row' },
  dash: { width: 30, height: 30, borderRadius: 15, borderWidth: 1.5, borderStyle: 'dashed', borderColor: 'rgba(255,255,255,0.28)' },
  endChip: { height: 34, paddingHorizontal: 12, borderRadius: 17, backgroundColor: 'rgba(255,255,255,0.07)', justifyContent: 'center' },
  field: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 34, paddingHorizontal: 12, borderRadius: 17, backgroundColor: 'rgba(255,179,71,0.14)' },
  tag: { height: 32, paddingHorizontal: 12, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.07)', justifyContent: 'center' },
});
