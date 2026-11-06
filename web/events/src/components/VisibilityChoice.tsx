import { Pressable, StyleSheet, View } from 'react-native';

import type { AudienceValue } from './AudiencePicker';
import { Chip, s, T } from './ui';
import { pressTransition } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';
import type { MemberGroup } from '@/lib/types';

/** Qui voit l'événement, en quatre choix simples (étape « Qui est invité » de l'assistant IA). */
export type Visibility = 'public' | 'vip' | 'group' | 'invite';
export const VISIBILITIES: readonly Visibility[] = ['public', 'vip', 'group', 'invite'];

export function visibilityOf(v: AudienceValue): Visibility {
  if (v.audience === 'public') return 'public';
  if (v.vip) return 'vip';
  return v.group_ids.length ? 'group' : 'invite';
}

/** Le même choix, appliqué : les personnes ajoutées une à une sont gardées, seuls le public et les groupes changent. */
export function withVisibility(v: AudienceValue, kind: Visibility, groupIds: string[] = []): AudienceValue {
  if (kind === 'public') return { ...v, audience: 'public', vip: false, group_ids: [] };
  if (kind === 'vip') return { ...v, audience: 'invite', vip: true, group_ids: [] };
  if (kind === 'group') return { ...v, audience: 'invite', vip: false, group_ids: groupIds };
  return { ...v, audience: 'invite', vip: false, group_ids: [] };
}

const TITLES: Record<Visibility, string> = {
  public: '🌍 Public + lien public',
  vip: '👥 Membres Vendredi Party',
  group: '👥 Un groupe',
  invite: '✉️ Sur invitation seulement',
};

/** Ce que veut dire le choix, en une phrase (montré en surbrillance, comme l'ancien bandeau de l'étape 1). */
export function visibilitySentence(kind: Visibility, groupNames: string[]): string {
  if (kind === 'public') return 'Tout le monde peut le voir : tous les comptes Party, et toute personne qui a le lien (elle répond après connexion par SMS).';
  if (kind === 'vip') return 'Tous les Membres VIP et au-dessus le voient, plus les personnes que tu invites ci-dessous.';
  if (kind === 'group') {
    return groupNames.length
      ? `Les membres de ${groupNames.map((n) => `« ${n} »`).join(', ')} le voient, plus les personnes que tu invites. Personne n’entre dans le groupe.`
      : 'Choisis le groupe qui le voit.';
  }
  return 'Seules les personnes que tu invites ci-dessous le voient.';
}

/** groups : seulement ceux dont la personne fait partie ; vipOk : elle est dans Vendredi Party (ou admin). */
export function VisibilityChoice({ value, onChange, groups, vipOk }: {
  value: AudienceValue; onChange: (v: AudienceValue) => void; groups: MemberGroup[]; vipOk: boolean;
}) {
  const kind = visibilityOf(value);
  const names = groups.filter((g) => value.group_ids.includes(g.id)).map((g) => g.name);
  const kinds = VISIBILITIES.filter((k) => (k !== 'group' || groups.length) && (k !== 'vip' || vipOk));
  const highlight = kind === 'public' ? st.bannerPublic : st.bannerOther;

  return (
    <View style={{ gap: 10 }}>
      <View style={[st.banner, highlight]} accessibilityLabel={`${TITLES[kind]} : ${visibilitySentence(kind, names)}`}>
        <T weight="bold" size={16}>{TITLES[kind]}{kind === 'group' && names.length ? ` · ${names.join(', ')}` : ''}</T>
        <T size={13} color={colors.text}>{visibilitySentence(kind, names)}</T>
      </View>
      <View style={{ gap: 6 }} accessibilityRole="radiogroup" accessibilityLabel="Qui voit l’événement">
        {kinds.map((k) => (
          <Pressable key={k} accessibilityRole="radio" accessibilityState={{ checked: kind === k }} aria-checked={kind === k} accessibilityLabel={TITLES[k]}
            onPress={() => onChange(withVisibility(value, k, k === 'group' ? (value.group_ids.length ? value.group_ids : groups.slice(0, 1).map((g) => g.id)) : []))}
            style={({ pressed }) => [st.option, pressTransition, kind === k && st.optionOn, pressed && { opacity: 0.85 }]}>
            <View style={[st.radio, kind === k && st.radioOn]} />
            <T weight={kind === k ? 'bold' : 'semibold'} size={15}>{TITLES[k]}</T>
          </Pressable>
        ))}
      </View>
      {kind === 'group' ? (
        <View style={s.wrap}>
          {groups.map((g) => (
            <Chip key={g.id} label={`${g.name} · ${g.member_group_members.length}`} selected={value.group_ids.includes(g.id)}
              onPress={() => {
                const next = value.group_ids.includes(g.id) ? value.group_ids.filter((x) => x !== g.id) : [...value.group_ids, g.id];
                onChange(withVisibility(value, next.length ? 'group' : 'invite', next));
              }} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  banner: { gap: 4, padding: 14, borderRadius: radius.md, borderWidth: 1.5 },
  bannerPublic: { backgroundColor: 'rgba(250,204,21,0.16)', borderColor: 'rgba(250,204,21,0.75)' },
  bannerOther: { backgroundColor: colors.accentDim, borderColor: '#8A2A5E' },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, paddingHorizontal: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  optionOn: { backgroundColor: colors.fillStrong },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.muted },
  radioOn: { borderColor: colors.action, borderWidth: 6 },
});
