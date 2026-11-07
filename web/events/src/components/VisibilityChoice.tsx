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

/** Le même choix, appliqué : les personnes ajoutées une à une sont gardées, seuls le public et les groupes changent. */
export function withVisibility(v: AudienceValue, kind: Visibility, groupIds: string[] = []): AudienceValue {
  if (kind === 'public') return { ...v, audience: 'public', vip: false, group_ids: [] };
  if (kind === 'vip') return { ...v, audience: 'invite', vip: true, group_ids: [] };
  if (kind === 'group') return { ...v, audience: 'invite', vip: false, group_ids: groupIds };
  return { ...v, audience: 'invite', vip: false, group_ids: [] };
}

export const TITLES: Record<Visibility, string> = {
  public: '🌍 Public + lien public',
  vip: '👥 Membres Vendredi Party',
  group: '👥 Un groupe',
  invite: '✉️ Sur invitation seulement',
};

/** Ce que veut dire le choix, en une phrase ; proposing : il faut d'abord la validation d'un admin. */
export function visibilitySentence(kind: Visibility, groupNames: string[], proposing = false): string {
  if (kind === 'public') return 'Tout le monde peut le voir : tous les comptes Party, et toute personne qui a le lien (elle répond après connexion par SMS).';
  if (kind === 'vip') return 'Tous les Membres VIP et au-dessus le voient. Tu pourras inviter d’autres personnes juste après.';
  if (kind === 'group') {
    return groupNames.length
      ? `Les membres de ${groupNames.map((n) => `« ${n} »`).join(', ')} le voient. Tu pourras inviter d’autres personnes juste après. Personne n’entre dans le groupe.`
      : 'Choisis le groupe qui le voit.';
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
  if (kind === 'group') return groupNames.length ? `Publier pour ${groupNames.map((n) => `« ${n} »`).join(', ')}` : 'Choisis un groupe';
  return 'Publier';
}

/**
 * Étape 2 « Qui est invité » (retour de l'admin, 06.11) : chaque choix est un bouton qui PUBLIE (ou envoie pour validation).
 * Sur invitation : la feuille « Inviter » s'ouvre ensuite avec le lien prêt ; un groupe ou les Membres : la fiche, carte
 * « Invités » en avant. Un groupe se choisit d'abord (puces), puis « Publier pour « Ski » ». suggested : le choix dit à
 * l'IA, mis en avant. groups : seulement ceux dont la personne fait partie ; vipOk : elle est dans Vendredi Party.
 */
export function PublishChoice({ groups, vipOk, suggested, suggestedGroups, proposing, busy, onPublish, announce, onAnnounce }: {
  groups: MemberGroup[]; vipOk: boolean; suggested: Visibility; suggestedGroups: string[]; proposing: boolean; busy: boolean;
  onPublish: (kind: Visibility, groupIds: string[]) => void;
  /** « Prévenir » (Membres Vendredi Party, un groupe) : un interrupteur par carte, éteints par défaut, jamais pour le public. */
  announce: { vip: boolean; group: boolean }; onAnnounce: (kind: 'vip' | 'group', on: boolean) => void;
}) {
  const kinds = VISIBILITIES.filter((k) => (k !== 'group' || groups.length) && (k !== 'vip' || vipOk));
  const [picking, setPicking] = useState(suggested === 'group');
  const [chosen, setChosen] = useState<string[]>(suggestedGroups.length ? suggestedGroups : groups.slice(0, 1).map((g) => g.id));
  const names = groups.filter((g) => chosen.includes(g.id)).map((g) => g.name);

  return (
    <View style={{ gap: 10 }}>
      {kinds.map((k) => {
        const on = k === suggested;
        const label = publishLabel(k, k === 'group' ? names : [], proposing);
        const press = () => (k === 'group' ? setPicking(true) : onPublish(k, []));
        return (
          <View key={k} style={[st.card, on && st.cardOn]}>
            <Pressable accessibilityRole="button" accessibilityLabel={k === 'group' ? TITLES.group : `${TITLES[k]} : ${label}`}
              accessibilityState={{ disabled: busy }} disabled={busy} onPress={press}
              style={({ pressed }) => [{ gap: 6 }, pressTransition, pressed && { opacity: 0.85, transform: [{ scale: 0.99 }] }]}>
              <View style={st.titleRow}>
                <T weight="bold" size={16} style={{ flex: 1 }}>{TITLES[k]}</T>
                {on ? <View style={st.tag}><T size={11} weight="bold" color={colors.onAction}>Suggéré</T></View> : null}
              </View>
              <T size={13} color={colors.textSoft}>{visibilitySentence(k, k === 'group' ? names : [], proposing)}</T>
              {k !== 'group' ? <T size={14} weight="bold" color={colors.accent}>{label} ›</T> : null}
            </Pressable>
            {k === 'vip' ? <AnnounceToggle groupIds={[]} vip label="Prévenir les Membres Vendredi Party" value={announce.vip}
              onChange={(on) => onAnnounce('vip', on)} disabled={busy} /> : null}
            {k === 'group' && picking ? (
              <View style={{ gap: 10 }}>
                <View style={s.wrap}>
                  {groups.map((g) => (
                    <Chip key={g.id} label={`${g.name} · ${g.member_group_members.length}`} selected={chosen.includes(g.id)}
                      onPress={() => setChosen((c) => (c.includes(g.id) ? c.filter((x) => x !== g.id) : [...c, g.id]))} />
                  ))}
                </View>
                <AnnounceToggle groupIds={chosen} label={names.length ? `Prévenir ${names.map((n) => `« ${n} »`).join(', ')}` : 'Prévenir le groupe'}
                  value={announce.group} onChange={(on) => onAnnounce('group', on)} disabled={busy} />
                <Button label={publishLabel('group', names, proposing)} disabled={!chosen.length || busy} loading={busy}
                  onPress={() => onPublish('group', chosen)} />
              </View>
            ) : k === 'group' ? <T size={14} weight="bold" color={colors.accent}>Choisir le groupe ›</T> : null}
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
