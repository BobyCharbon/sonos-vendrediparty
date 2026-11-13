import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AnnounceToggle } from './AnnounceToggle';
import type { AudienceValue } from './AudiencePicker';
import { Button, Chip, s, T } from './ui';
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

/** Le même choix, appliqué : les personnes ajoutées une à une sont gardées, seuls le public et les groupes changent.
 * « Des groupes » : les Membres Vendredi Party (vip) et/ou des groupes, ensemble (retour de l'admin, 11.11). */
export function withVisibility(v: AudienceValue, kind: Visibility, groupIds: string[] = [], vip = kind === 'vip'): AudienceValue {
  if (kind === 'public') return { ...v, audience: 'public', vip: false, group_ids: [] };
  if (kind === 'vip' || kind === 'group') return { ...v, audience: 'invite', vip, group_ids: groupIds };
  return { ...v, audience: 'invite', vip: false, group_ids: [] };
}

/** Nom du choix « Membres Vendredi Party » parmi les puces des groupes. */
export const VIP_NAME = 'Membres Vendredi Party';
const VIP_CHIP = '__vip__';

export const TITLES: Record<Visibility, string> = {
  public: '🌍 Public + lien public',
  vip: '👥 Membres Vendredi Party',
  group: '👥 Des groupes',
  invite: '✉️ Sur invitation seulement',
};

/** Ce que veut dire le choix, en une phrase ; proposing : il faut d'abord la validation d'un admin. */
export function visibilitySentence(kind: Visibility, groupNames: string[], proposing = false): string {
  if (kind === 'public') return 'Tout le monde peut le voir : tous les comptes Party, et toute personne qui a le lien (elle répond après connexion par SMS).';
  if (kind === 'vip') return 'Tous les Membres VIP et au-dessus le voient. Tu pourras inviter d’autres personnes juste après.';
  if (kind === 'group') {
    return groupNames.length
      ? `Les membres de ${groupNames.map((n) => `« ${n} »`).join(', ')} le voient. Tu pourras inviter d’autres personnes juste après. Personne n’entre dans le groupe.`
      : 'Coche un ou plusieurs groupes, puis publie.';
  }
  return proposing
    ? 'Seules les personnes que tu invites le voient. Le lien à partager arrive dès qu’un admin a validé.'
    : 'Seules les personnes que tu invites le voient. Le lien à partager s’ouvre tout de suite : WhatsApp, Messages, QR code.';
}

/** Ce que fait le toucher (le bouton le dit : jamais de publication surprise). */
export function publishLabel(kind: Visibility, groupNames: string[], proposing: boolean): string {
  if (proposing) return 'Envoyer pour validation';
  if (kind === 'invite') return 'Publier et envoyer le lien';
  if (kind === 'vip') return 'Publier pour les Membres Vendredi Party';
  if (kind === 'group') {
    if (groupNames.length === 1 && groupNames[0] === VIP_NAME) return 'Publier pour les Membres Vendredi Party';
    return groupNames.length ? `Publier pour ${groupNames.map((n) => `« ${n} »`).join(', ')}` : 'Choisis au moins un groupe';
  }
  return 'Publier';
}

/**
 * Étape 2 « Qui est invité » (retours de l'admin, 06.11 et 11.11) : public et « sur invitation » publient (ou envoient pour
 * validation) d'un toucher ; « Des groupes » s'ouvre d'abord : on coche les Membres Vendredi Party et/ou un ou plusieurs
 * groupes, puis « Publier pour … ». suggested : le choix dit à l'IA, mis en avant. groups : seulement ceux dont la personne
 * fait partie ; vipOk : elle est dans Vendredi Party. Un seul « Prévenir » pour tous les groupes cochés (éteint par défaut).
 */
export function PublishChoice({ groups, vipOk, suggested, suggestedGroups, proposing, busy, onPublish, announce, onAnnounce }: {
  groups: MemberGroup[]; vipOk: boolean; suggested: Visibility; suggestedGroups: string[]; proposing: boolean; busy: boolean;
  onPublish: (kind: Visibility, groupIds: string[], vip: boolean) => void;
  /** « Prévenir » les groupes cochés (Membres Vendredi Party compris) : éteint par défaut, jamais pour le public. */
  announce: boolean; onAnnounce: (on: boolean) => void;
}) {
  const shown: Visibility = suggested === 'vip' ? 'group' : suggested;
  const kinds = VISIBILITIES.filter((k) => k !== 'vip' && (k !== 'group' || groups.length || vipOk));
  const [picking, setPicking] = useState(shown === 'group');
  const [chosen, setChosen] = useState<string[]>(() => {
    if (suggested === 'vip' && vipOk) return [VIP_CHIP];
    if (suggestedGroups.length) return suggestedGroups;
    return vipOk ? [VIP_CHIP] : groups.slice(0, 1).map((g) => g.id);
  });
  const vip = vipOk && chosen.includes(VIP_CHIP);
  const groupIds = chosen.filter((id) => id !== VIP_CHIP && groups.some((g) => g.id === id));
  const names = [...(vip ? [VIP_NAME] : []), ...groups.filter((g) => groupIds.includes(g.id)).map((g) => g.name)];
  const chips = [...(vipOk ? [{ id: VIP_CHIP, label: `👥 ${VIP_NAME}` }] : []),
    ...groups.map((g) => ({ id: g.id, label: `${g.name} · ${g.member_group_members.length}` }))];
  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  const announceLabel = names.length === 1 && vip ? 'Prévenir les Membres Vendredi Party'
    : names.length ? `Prévenir ${names.map((n) => `« ${n} »`).join(', ')}` : 'Prévenir le groupe';

  return (
    <View style={{ gap: 10 }}>
      {kinds.map((k) => {
        const on = k === shown;
        const label = publishLabel(k, k === 'group' ? names : [], proposing);
        const press = () => (k === 'group' ? setPicking(true) : onPublish(k, [], false));
        return (
          <View key={k} style={[st.card, on && st.cardOn]}>
            <Pressable accessibilityRole="button" accessibilityLabel={k === 'group' ? TITLES.group : `${TITLES[k]} : ${label}`}
              accessibilityState={{ disabled: busy, expanded: k === 'group' ? picking : undefined }} disabled={busy} onPress={press}
              style={({ pressed }) => [{ gap: 6 }, pressTransition, pressed && { opacity: 0.85, transform: [{ scale: 0.99 }] }]}>
              <View style={st.titleRow}>
                <T weight="bold" size={16} style={{ flex: 1 }}>{TITLES[k]}</T>
                {on ? <View style={st.tag}><T size={11} weight="bold" color={colors.onAction}>Suggéré</T></View> : null}
              </View>
              <T size={13} color={colors.textSoft}>{visibilitySentence(k, k === 'group' ? names : [], proposing)}</T>
              {k !== 'group' ? <T size={14} weight="bold" color={colors.accent}>{label} ›</T> : null}
            </Pressable>
            {k === 'group' && picking ? (
              <View style={{ gap: 10 }}>
                <T size={13} weight="bold" color={colors.textSoft}>Coche autant de groupes que tu veux</T>
                <View style={s.wrap}>
                  {chips.map((c) => <Chip key={c.id} label={c.label} selected={chosen.includes(c.id)} onPress={() => toggle(c.id)} />)}
                </View>
                <AnnounceToggle groupIds={groupIds} vip={vip} label={announceLabel} value={announce} onChange={onAnnounce} disabled={busy} />
                <Button label={publishLabel('group', names, proposing)} disabled={!names.length || busy} loading={busy}
                  onPress={() => onPublish(vip && !groupIds.length ? 'vip' : 'group', groupIds, vip)} />
              </View>
            ) : k === 'group' ? <T size={14} weight="bold" color={colors.accent}>Choisir les groupes ›</T> : null}
          </View>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  card: { gap: 10, padding: 14, borderRadius: radius.md, backgroundColor: colors.fill, borderWidth: 1.5, borderColor: 'transparent' },
  cardOn: { backgroundColor: colors.accentDim, borderColor: '#8A2A5E' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  tag: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, backgroundColor: colors.action },
});
