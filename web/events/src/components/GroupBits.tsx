import { router } from 'expo-router';
import type { ReactNode } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { Avatar, T } from './ui';
import { BADGE_RED } from '@/lib/activityBadge';
import { dateTile, plural } from '@/lib/format';
import { GROUP_EMOJIS, gradient, groupName, palette, useGroupImage, type GroupLook, type GroupOverview } from '@/lib/groups';
import { ease, enter, pressTransition, reducedMotion } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * Pièces du nouveau graphisme des groupes (17.11, maquette A « Néon & couvertures » + bulles de B) : tuile emoji sur le
 * dégradé du groupe, ligne façon WhatsApp, grande carte « Crée le groupe de ta bande », état vide, bulles « Tes groupes »
 * de l'onglet Événements, étiquette du groupe sur les cartes d'événement.
 */

// Animations propres aux groupes (web, CSS : transform et opacity seulement ; rien avec « Réduire les animations »).
type WebStyle = ViewStyle & Record<string, unknown>;
const web = (style: WebStyle) => style as ViewStyle;
const loops = StyleSheet.create({
  floaty: web({
    animationKeyframes: [{ '0%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-8px)' }, '100%': { transform: 'translateY(0)' } }],
    animationDuration: '4200ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
  shine: web({
    animationKeyframes: [{ '0%': { transform: 'translateX(-120%) skewX(-20deg)' }, '55%': { transform: 'translateX(320%) skewX(-20deg)' },
      '100%': { transform: 'translateX(320%) skewX(-20deg)' } }],
    animationDuration: '3600ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
  orbit: web({
    animationKeyframes: [{ from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } }],
    animationDuration: '40s', animationTimingFunction: 'linear', animationIterationCount: 'infinite',
  }),
  pulse: web({
    animationKeyframes: [{ '0%': { transform: 'scale(1)' }, '60%': { transform: 'scale(1.12)' }, '100%': { transform: 'scale(1)' } }],
    animationDuration: '2200ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
});

/** Boucle décorative (flottement, reflet), décalée ; rien si « Réduire les animations ». */
export function loop(kind: keyof typeof loops, delayMs = 0): ViewStyle | undefined {
  if (reducedMotion) return undefined;
  return delayMs ? ([loops[kind], web({ animationDelay: `${delayMs}ms` })] as unknown as ViewStyle) : loops[kind];
}

type TileGroup = { emoji: string; color?: string | null; photo?: string | null; photo_path?: string | null;
  system?: boolean | null; system_key?: string | null };

/** Tuile du groupe : sa photo (ou le logo de Party pour Membres Vendredi Party), sinon son emoji sur le dégradé de sa
 * couleur ; liseré clair, ombre colorée. */
export function GroupTile({ group, size = 52, style, src }: { group: TileGroup; size?: number; style?: StyleProp<ViewStyle>; src?: string | null }) {
  const p = palette(group.color);
  const fromGroup = useGroupImage(group);
  const image = src ?? fromGroup;  // src : photo choisie, pas encore envoyée
  return (
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
      style={[{ width: size, height: size, borderRadius: size * 0.3, alignItems: 'center', justifyContent: 'center',
        borderWidth: 2, borderColor: 'rgba(255,255,255,0.28)', shadowColor: p.to, shadowOpacity: 0.45, shadowRadius: size * 0.22,
        shadowOffset: { width: 0, height: size * 0.08 } }, gradient(group.color), style]}>
      {image
        ? <Image source={{ uri: image }} testID="group-photo" style={{ width: '100%', height: '100%', borderRadius: size * 0.3 - 2 }} resizeMode="cover" />
        : <Text style={{ fontSize: size * 0.5, lineHeight: size * 0.62 }}>{group.emoji}</Text>}
    </View>
  );
}

/** Étiquette du groupe (carte d'événement, page du groupe) : emoji + nom, sur la teinte du groupe. */
export function GroupTag({ group, onPress }: { group: GroupLook; onPress?: () => void }) {
  const p = palette(group.color);
  const body = (
    <View style={[st.tag, { backgroundColor: p.dim, borderColor: `${p.main}55` }]}>
      <Text style={{ fontSize: 12 }}>{group.emoji}</Text>
      <T size={12} weight="bold" color={p.text} numberOfLines={1} style={{ flexShrink: 1 }}>{groupName(group)}</T>
    </View>
  );
  if (!onPress) return <View accessibilityLabel={`Groupe ${groupName(group)}`}>{body}</View>;
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={`Groupe ${groupName(group)}`} onPress={onPress}
      style={({ pressed }) => [pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>{body}</Pressable>
  );
}

/** Pastille rouge des non-lus (respire doucement, se pose à chaque nouveau compte). */
export function UnreadBadge({ count, style }: { count: number; style?: StyleProp<ViewStyle> }) {
  if (!count) return null;
  return (
    <View key={count} style={[st.badge, enter('pop'), style]}>
      <Text style={st.badgeText}>{count > 99 ? '99+' : count}</Text>
    </View>
  );
}

/** « Sam. 22 nov. · Match + apéro » : le prochain événement du groupe, en une ligne. */
export function nextEventLine(e: NonNullable<GroupOverview['next_event']>): string {
  if (e.date_mode === 'poll' || !e.starts_at) return `🗳️ Sondage · ${e.title}`;
  const d = dateTile(e.starts_at);
  const wd = d.weekday.charAt(0) + d.weekday.slice(1).toLowerCase();
  return `📅 ${wd} ${d.day} ${d.month.toLowerCase()} · ${e.title}`;
}

/** Heure façon WhatsApp : « 21:14 » aujourd'hui, « hier », « lun. », puis « 3 nov. ». */
export function chatTime(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000);
  if (days <= 0) return d.toLocaleTimeString('fr-CH', { hour: '2-digit', minute: '2-digit' });
  if (days === 1) return 'hier';
  if (days < 7) return d.toLocaleDateString('fr-CH', { weekday: 'short' });
  // « 31 oct. » (jamais « 31 oct. à » coupé, vu en recette iPhone du 17.11) ; une autre année : « 31.10.25 ».
  return d.getFullYear() === now.getFullYear()
    ? d.toLocaleDateString('fr-CH', { day: 'numeric', month: 'short' })
    : d.toLocaleDateString('fr-CH', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

/** Ligne de la liste des groupes (maquette A) : filet de couleur, tuile, nom, heure, dernier message, non lus,
 * prochain événement (ou « Aucun événement prévu »). Vendredi Party : 🔒 Toute la communauté. */
export function GroupRow({ group, index = 0 }: { group: GroupOverview; index?: number }) {
  const p = palette(group.color);
  const name = groupName(group);
  return (
    <Pressable accessibilityRole="link"
      accessibilityLabel={`${name}${group.unread ? `, ${group.unread} non lus` : ''}`}
      testID={`group-row-${group.id}`}
      onPress={() => router.push(`/group/${group.id}`)}
      style={({ pressed }) => [st.row, group.system && st.rowSystem, enter('rise', index), pressTransition,
        pressed && { transform: [{ scale: 0.98 }], backgroundColor: colors.surface2 }]}>
      <View style={[st.rowEdge, { backgroundColor: p.main }]} />
      <GroupTile group={group} size={52} />
      <View style={{ flex: 1, minWidth: 0, gap: 3 }}>
        <View style={st.rowTop}>
          <T weight="bold" size={16} numberOfLines={1} style={{ flex: 1 }}>{name}</T>
          {group.last_at ? (
            <T size={12} weight={group.unread ? 'bold' : 'body'} color={group.unread ? colors.accent : colors.muted}>{chatTime(group.last_at)}</T>
          ) : null}
        </View>
        <View style={st.rowTop}>
          <T size={14} color={colors.textSoft} numberOfLines={1} style={{ flex: 1 }}>
            {group.last ? (
              <>{group.last_by ? <T size={14} weight="bold" color={colors.text}>{group.last_by} : </T> : null}{group.last}</>
            ) : group.member ? 'Aucun message : dis bonjour !' : 'Tu ne fais pas partie de ce groupe'}
          </T>
          <UnreadBadge count={group.unread} />
        </View>
        {group.system ? (
          <T size={12} weight="bold" color={p.text}>🔒 Toute la communauté · {group.members}</T>
        ) : (
          <View style={[st.next, { backgroundColor: group.next_event ? p.dim : colors.fill }]}>
            <T size={12} weight="bold" color={group.next_event ? p.text : colors.muted} numberOfLines={1}>
              {group.next_event ? nextEventLine(group.next_event) : 'Aucun événement prévu'}
            </T>
          </View>
        )}
      </View>
    </Pressable>
  );
}

/** Emojis qui flottent (grande carte, état vide, couvertures) : pure décoration, cachés aux lecteurs d'écran. */
export function FloatingEmojis({ items }: { items: { emoji: string; top: number | string; left?: number | string; right?: number | string; size: number; rotate?: number; delay?: number; opacity?: number }[] }) {
  return (
    <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={StyleSheet.absoluteFill}>
      {items.map((it, i) => (
        <View key={i} style={[{ position: 'absolute', top: it.top as number, left: it.left as number, right: it.right as number,
          opacity: it.opacity ?? 1 }, loop('floaty', it.delay ?? i * 500)]}>
          <Text style={{ fontSize: it.size, transform: [{ rotate: `${it.rotate ?? 0}deg` }] }}>{it.emoji}</Text>
        </View>
      ))}
    </View>
  );
}

/** Grande carte rose « Crée le groupe de ta bande » (en tête de la liste, jamais imposée). */
export function CreateGroupHero() {
  return (
    <View style={[st.hero, gradient('pink', 125), enter('rise')]}>
      <View pointerEvents="none" style={[st.heroShine, loop('shine')]} />
      <FloatingEmojis items={[
        { emoji: '⚽', top: 16, right: 64, size: 30, rotate: -8 },
        { emoji: '🪩', top: 44, right: 18, size: 34, rotate: 6, delay: 700 },
        { emoji: '🏡', top: 96, right: 52, size: 28, rotate: -4, delay: 1300 },
      ]} />
      <View style={{ maxWidth: '68%', gap: 6 }}>
        <Text role="heading" style={st.heroTitle}>Crée le groupe de ta bande</Text>
        <T size={14} color="rgba(255,255,255,0.92)">Potes, club, famille : un toucher pour inviter tout le monde à tes soirées.</T>
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel="Créer un groupe" testID="group-create-hero"
        onPress={() => router.push('/group/new')}
        style={({ pressed }) => [st.heroButton, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
        <T size={16} weight="bold" color={colors.action}>＋  Créer un groupe</T>
      </Pressable>
    </View>
  );
}

const INSPIRATIONS: { emoji: string; name: string; color: string }[] = [
  { emoji: '⚽', name: 'Les potes du foot', color: 'mint' },
  { emoji: '🪩', name: 'Soirées du vendredi', color: 'pink' },
  { emoji: '🏡', name: 'La famille', color: 'coral' },
  { emoji: '🍕', name: 'Pizza du jeudi', color: 'lemon' },
];

/** État vide (aucun groupe) : une bande en orbite, ce que le groupe apporte, des idées de noms, « Créer mon groupe ». */
export function EmptyGroups() {
  const benefits: [string, string, string][] = [
    ['👋', 'Invite tout le monde d’un toucher', 'Ton événement arrive chez chaque membre.'],
    ['💬', 'Discutez entre vous', 'Une discussion de groupe, photos et vocaux.'],
    ['📅', 'Les événements du groupe', 'Tous réunis sur la page du groupe.'],
  ];
  const orbit = ['⚽', '🪩', '🏡', '🎲', '🥾'];
  return (
    <View style={{ gap: 18 }} testID="groups-empty">
      <View style={st.orbitWrap} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <View style={st.orbitRing} />
        <View style={[StyleSheet.absoluteFill, loop('orbit')]}>
          {orbit.map((e, i) => {
            const a = (i / orbit.length) * Math.PI * 2 - Math.PI / 2;
            return (
              <View key={e} style={[st.orbitDot, { left: 110 + Math.cos(a) * 92 - 24, top: 110 + Math.sin(a) * 92 - 24 }]}>
                <Text style={{ fontSize: 22 }}>{e}</Text>
              </View>
            );
          })}
        </View>
        <View style={loop('pulse')}><GroupTile group={{ emoji: '👯', color: 'pink' }} size={92} /></View>
      </View>
      <View style={{ gap: 6, alignItems: 'center' }}>
        <Text role="heading" style={[st.heroTitle, { textAlign: 'center', fontSize: 28 }]}>Ta bande mérite son groupe</Text>
        <T muted style={{ textAlign: 'center' }}>Tes gens au même endroit, et tes soirées s’organisent toutes seules.</T>
      </View>
      <View style={{ gap: 2 }}>
        {benefits.map(([icon, title, hint], i) => (
          <View key={title} style={[st.benefit, i ? { borderTopWidth: 1, borderTopColor: colors.line } : null, enter('rise', i + 1)]}>
            <View style={st.benefitIcon}><Text style={{ fontSize: 18 }}>{icon}</Text></View>
            <View style={{ flex: 1 }}>
              <T weight="bold">{title}</T>
              <T muted size={13}>{hint}</T>
            </View>
          </View>
        ))}
      </View>
      <T size={13} weight="bold" color={colors.muted} style={st.label}>POUR T’INSPIRER</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -16, flexGrow: 0 }}
        contentContainerStyle={{ gap: 8, paddingHorizontal: 16 }}>
        {INSPIRATIONS.map((it) => (
          <Pressable key={it.name} accessibilityRole="button" accessibilityLabel={`Créer « ${it.name} »`}
            onPress={() => router.push({ pathname: '/group/new', params: { name: it.name, emoji: it.emoji, color: it.color } })}
            style={({ pressed }) => [st.idea, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
            <Text style={{ fontSize: 16 }}>{it.emoji}</Text>
            <T size={14} weight="semibold">{it.name}</T>
          </Pressable>
        ))}
      </ScrollView>
      <Pressable accessibilityRole="button" accessibilityLabel="Créer mon groupe" testID="group-create-empty" onPress={() => router.push('/group/new')}
        style={({ pressed }) => [st.cta, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
        <T size={16} weight="bold" color={colors.onAction}>＋  Créer mon groupe</T>
      </Pressable>
      <T muted size={13} style={{ textAlign: 'center' }}>Un ami t’a envoyé un lien ? Ouvre-le : tu rejoins son groupe directement.</T>
    </View>
  );
}

/** Une bulle « story » : anneau aux couleurs du groupe, emoji au centre, nom dessous, pastille des non-lus. */
function Bubble({ label, children, onPress, ring, a11y, badge = 0, index }: {
  label: string; children: ReactNode; onPress: () => void; ring?: ViewStyle; a11y: string; badge?: number; index: number;
}) {
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={a11y} onPress={onPress}
      style={({ pressed }) => [st.bubble, enter('pop', index), pressTransition, pressed && { transform: [{ scale: 0.93 }] }]}>
      <View style={[st.bubbleRing, ring]}>
        <View style={st.bubbleInner}>{children}</View>
        <UnreadBadge count={badge} style={st.bubbleBadge} />
      </View>
      <T size={12} weight="semibold" color={colors.textSoft} numberOfLines={2} style={{ textAlign: 'center' }}>{label}</T>
    </Pressable>
  );
}

/** Intérieur d'une bulle : la photo du groupe (ou le logo de Party), sinon son emoji. */
function BubbleFace({ group }: { group: GroupOverview }) {
  const image = useGroupImage(group);
  return (
    <View style={[st.plus, { backgroundColor: palette(group.color).dim, overflow: 'hidden' }]}>
      {image ? <Image source={{ uri: image }} style={{ width: '100%', height: '100%' }} resizeMode="cover" />
        : <Text style={{ fontSize: 28 }}>{group.emoji}</Text>}
    </View>
  );
}

/** Bulles « Tes groupes » en haut de l'onglet Événements (direction B) : « + Crée ton groupe » d'abord, puis mes groupes. */
export function GroupBubbles({ groups }: { groups: GroupOverview[] }) {
  return (
    <View testID="group-bubbles" accessibilityLabel="Tes groupes">
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -16, flexGrow: 0 }}
        contentContainerStyle={{ gap: 10, paddingHorizontal: 16, paddingTop: 6 }}>
        <Bubble label="Crée ton groupe" a11y="Crée ton groupe" index={0} onPress={() => router.push('/group/new')}
          ring={{ borderStyle: 'dashed', borderColor: colors.mint, backgroundColor: 'transparent' }}>
          <View style={[st.plus, { backgroundColor: colors.mintDim }]}><T size={26} weight="bold" color={colors.mint}>+</T></View>
        </Bubble>
        {groups.map((g, i) => (
          <Bubble key={g.id} index={i + 1} label={groupName(g)} badge={g.unread}
            a11y={`Groupe ${groupName(g)}${g.unread ? `, ${g.unread} non lus` : ''}`} onPress={() => router.push(`/group/${g.id}`)}
            ring={{ ...gradient(g.color), borderColor: 'transparent' }}>
            <BubbleFace group={g} />
          </Bubble>
        ))}
        <Bubble label="Tout voir" a11y="Tous mes groupes" index={groups.length + 1} onPress={() => router.push('/groups')}
          ring={{ borderColor: colors.lineStrong, backgroundColor: 'transparent' }}>
          <View style={[st.plus, { backgroundColor: colors.surface }]}><T size={20} weight="bold" color={colors.textSoft}>›</T></View>
        </Bubble>
      </ScrollView>
    </View>
  );
}

/** Visages des membres en pile (« MA IN YA +9 »). */
export function FaceStack({ faces, total, size = 30 }: { faces: GroupOverview['faces']; total: number; size?: number }) {
  const rest = total - faces.length;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }} accessibilityLabel={`${plural(total, 'membre')} : ${faces.map((f) => f.name).join(', ')}`}>
      {faces.map((f, i) => (
        <View key={f.id} style={{ marginLeft: i ? -size * 0.28 : 0, borderRadius: 999, borderWidth: 2, borderColor: colors.bg }}>
          <Avatar id={f.id} name={f.name} photo={f.avatar_url} size={size} profile={false} />
        </View>
      ))}
      {rest > 0 ? (
        <View style={[st.more, { width: size + 4, height: size + 4, borderRadius: (size + 4) / 2, marginLeft: -size * 0.28 }]}>
          <T size={11} weight="bold" color={colors.textSoft}>+{rest}</T>
        </View>
      ) : null}
    </View>
  );
}

/** Choix de l'emoji (liste fermée) : la sélection se pose avec un petit rebond. */
export function EmojiPicker({ value, onChange }: { value: string; onChange: (e: string) => void }) {
  return (
    <View style={st.pickRow} accessibilityRole="radiogroup" accessibilityLabel="Un emoji">
      {GROUP_EMOJIS.map((e) => {
        const on = e === value;
        return (
          <Pressable key={e} accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} accessibilityLabel={`Emoji ${e}`}
            onPress={() => onChange(e)}
            style={({ pressed }) => [st.emojiCell, on && st.emojiOn, pressTransition, pressed && { transform: [{ scale: 0.9 }] }]}>
            <View key={on ? 'on' : 'off'} style={on ? enter('pop') : undefined}><Text style={{ fontSize: 22 }}>{e}</Text></View>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Choix de la couleur (6 couleurs de Party). */
export function ColorPicker({ value, onChange, colorsList }: { value: string; onChange: (c: string) => void; colorsList: string[] }) {
  return (
    <View style={[st.pickRow, { gap: 12 }]} accessibilityRole="radiogroup" accessibilityLabel="Une couleur">
      {colorsList.map((c) => {
        const on = c === value;
        return (
          <Pressable key={c} accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} accessibilityLabel={`Couleur ${palette(c).name}`}
            onPress={() => onChange(c)}
            style={({ pressed }) => [st.colorRing, on && { borderColor: colors.text }, pressTransition, pressed && { transform: [{ scale: 0.9 }] }]}>
            <View style={[st.colorDot, gradient(c)]} />
          </Pressable>
        );
      })}
    </View>
  );
}


const st = StyleSheet.create({
  label: { letterSpacing: 0.8 },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', maxWidth: '100%', minHeight: 24,
    paddingHorizontal: 9, borderRadius: 12, borderWidth: 1 },
  badge: { minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 11, backgroundColor: BADGE_RED, alignItems: 'center', justifyContent: 'center' },
  badgeText: { color: '#FFFFFF', fontSize: 12, ...font.bold },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, paddingLeft: 14, borderRadius: radius.lg,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, overflow: 'hidden' },
  rowSystem: { backgroundColor: '#2A2148', borderColor: '#4A3F78' },
  rowEdge: { position: 'absolute', left: 0, top: 10, bottom: 10, width: 4, borderTopRightRadius: 3, borderBottomRightRadius: 3 },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  next: { alignSelf: 'flex-start', maxWidth: '100%', marginTop: 3, paddingHorizontal: 9, paddingVertical: 3, borderRadius: 10 },
  hero: { minHeight: 196, padding: 18, gap: 14, borderRadius: 24, overflow: 'hidden', justifyContent: 'space-between',
    shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 24, shadowOffset: { width: 0, height: 10 } },
  heroShine: { position: 'absolute', top: 0, bottom: 0, left: 0, width: '40%', backgroundColor: 'rgba(255,255,255,0.18)' },
  heroTitle: { color: '#FFFFFF', fontSize: 24, lineHeight: 27, ...font.display, letterSpacing: -0.4 },
  heroButton: { alignSelf: 'flex-start', minHeight: 46, paddingHorizontal: 18, borderRadius: 23, backgroundColor: '#FFFFFF',
    alignItems: 'center', justifyContent: 'center' },
  orbitWrap: { width: 220, height: 220, alignSelf: 'center', alignItems: 'center', justifyContent: 'center' },
  orbitRing: { position: 'absolute', width: 184, height: 184, borderRadius: 92, borderWidth: 1, borderColor: colors.lineStrong, borderStyle: 'dashed' },
  orbitDot: { position: 'absolute', width: 48, height: 48, borderRadius: 16, backgroundColor: colors.surface2, alignItems: 'center',
    justifyContent: 'center', borderWidth: 1, borderColor: colors.lineStrong },
  benefit: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  benefitIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  idea: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 44, paddingHorizontal: 14, borderRadius: 22,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  cta: { minHeight: 52, borderRadius: radius.md, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center',
    shadowColor: colors.action, shadowOpacity: 0.45, shadowRadius: 18, shadowOffset: { width: 0, height: 6 } },
  bubble: { width: 76, alignItems: 'center', gap: 6 },
  bubbleRing: { width: 68, height: 68, borderRadius: 34, padding: 3, borderWidth: 2, borderColor: 'transparent', alignItems: 'center', justifyContent: 'center' },
  bubbleInner: { width: '100%', height: '100%', borderRadius: 34, backgroundColor: colors.bg, padding: 2, alignItems: 'center', justifyContent: 'center' },
  bubbleBadge: { position: 'absolute', top: -4, right: -4, borderWidth: 2, borderColor: colors.bg },
  plus: { width: '100%', height: '100%', borderRadius: 30, alignItems: 'center', justifyContent: 'center' },
  more: { backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.bg },
  pickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  emojiCell: { width: 44, height: 44, borderRadius: 14, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: 'transparent' },
  emojiOn: { borderColor: colors.accent, backgroundColor: colors.accentDim },
  colorRing: { width: 46, height: 46, borderRadius: 23, padding: 3, borderWidth: 2, borderColor: 'transparent' },
  colorDot: { width: '100%', height: '100%', borderRadius: 20 },
});
