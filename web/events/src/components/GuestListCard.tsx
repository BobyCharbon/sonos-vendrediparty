import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { InviteSheet } from './InviteSheet';
import { Avatar, ErrorText, Meter, Skeleton, T, Toast } from './ui';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import {
  copyText, decideJoinRequest, fetchGuestList, filterGuests, filterLinks, guestCounts, guestOrigin, inviteLinkUrl, inviteMessage, linkLine, linkSpokenNames, linkTitle, nudgeInvitees,
  nudgeLink, removeInvitee, ruleSentence, shareInvite, statusWords, stopLink, unlimited,
  type Guest, type GuestFilter, type GuestList, type JoinRequest, type SentLink,
} from '@/lib/invites';
import { pressTransition } from '@/lib/motion';
import { colors, radius, rsvpColors } from '@/lib/theme';
import type { EventRow } from '@/lib/types';

type Ev = Pick<EventRow, 'id' | 'title' | 'starts_at' | 'ends_at' | 'all_day' | 'status' | 'announce_group'>;
type Me = { id: string; display_name: string };

const NONE_COLOR = colors.lavender;
const UNOPENED_COLOR = colors.muted;
const ACTION_WIDTH = 92;

/** Les cinq compteurs : ce sont aussi les filtres (un toucher filtre, un second revient à tout). */
const TILES: { key: Exclude<GuestFilter, 'all'>; label: string; color: string }[] = [
  { key: 'yes', label: 'Viennent', color: rsvpColors.yes },
  { key: 'maybe', label: 'Peut-être', color: rsvpColors.maybe },
  { key: 'no', label: 'Absents', color: rsvpColors.no },
  { key: 'none', label: 'Pas répondu', color: NONE_COLOR },
  { key: 'unopened', label: 'Lien pas ouvert', color: UNOPENED_COLOR },
];

const when = (ev: Ev) => (ev.starts_at ? formatShort(ev.starts_at).toLowerCase() : null);

/**
 * Carte « Invités » de la fiche (organisateurs, bêta invites_v2) : d'un coup d'œil qui vient, qui n'a pas encore répondu,
 * à qui on a envoyé un lien et qui a invité qui. « + » ouvre la feuille « Inviter » ; « Relancer » envoie une notification
 * Party (si la personne a l'app) ou ouvre la feuille de partage avec un message prêt ; glisser une ligne : Relancer, Retirer.
 */
export function GuestListCard({ event, me, onChanged, openSheet = false, headline, initialPeople = [], quietOnError = false }: {
  event: Ev; me: Me; onChanged: () => void;
  /** Vue d'un invité : liste illisible → rien du tout (sa réponse et la fiche restent), jamais une carte d'erreur. */
  quietOnError?: boolean;
  /** Juste publié « Sur invitation » (assistant IA) : la feuille « Inviter » s'ouvre aussitôt, lien prêt. */
  openSheet?: boolean; headline?: string; initialPeople?: string[];
}) {
  const [filter, setFilter] = useState<GuestFilter>('all');
  const [sheet, setSheet] = useState(openSheet);
  // Repliée par défaut (demande de l'admin, 12.11) : l'essentiel en deux lignes, le détail au toucher.
  const [expanded, setExpanded] = useState(false);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: list, reload, error: loadError } = useQuery(() => fetchGuestList(event.id), [event.id]);

  const refresh = () => { reload(); onChanged(); };
  const host = me.display_name.trim() || 'Moi';

  async function run(job: () => Promise<string | null>) {
    setError(null);
    try {
      const message = await job();
      if (message) setNote(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    reload();
  }

  /** Relancer une personne : notification Party si elle a l'app, sinon la feuille de partage avec son lien. */
  const nudge = (g: Guest) => run(async () => {
    const result = await nudgeInvitees(event.id, [g.id]);
    if (result.notified) return `${g.name} a reçu un rappel dans Party`;
    if (result.skipped) return `${g.name} a déjà été relancé aujourd’hui`;
    const url = g.link_token ? inviteLinkUrl(g.link_token) : `${location.origin}/events/event/${event.id}`;
    const shared = await shareInvite(inviteMessage({ name: g.name, host, title: event.title, when: when(event), url, nudge: true }), url, event.title);
    return shared === 'copied' ? 'Message copié : colle-le dans WhatsApp ou Messages' : null;
  });

  // Seulement ceux qui ont l'app : les autres ne reçoivent rien d'ici, ils ne sont donc jamais notés « relancés »
  // (leur bouton « Relancer », qui ouvre le partage avec leur lien, reste sur leur ligne).
  const nudgeAll = (people: Guest[]) => run(async () => {
    const reachable = people.filter((p) => p.has_app);
    const withoutApp = people.length - reachable.length;
    const result = reachable.length ? await nudgeInvitees(event.id, reachable.map((p) => p.id)) : { notified: 0, skipped: 0, share: [] };
    const parts = [result.notified ? `${result.notified} ${result.notified > 1 ? 'rappels envoyés' : 'rappel envoyé'} dans Party` : null,
      withoutApp + result.share.length ? `${withoutApp + result.share.length} sans l’app : relance-les une par une (« Relancer » sur leur ligne)` : null,
      result.skipped ? `${result.skipped} déjà relancé${result.skipped > 1 ? 's' : ''} aujourd’hui` : null].filter(Boolean);
    return parts.join(' · ') || 'Personne à relancer';
  });

  const nudgeByLink = (l: SentLink) => run(async () => {
    await nudgeLink(l.token);
    const url = inviteLinkUrl(l.token);
    const shared = await shareInvite(inviteMessage({ name: l.label, host, title: event.title, when: when(event), url, nudge: true }), url, event.title);
    return shared === 'copied' ? 'Message copié : colle-le dans WhatsApp ou Messages' : null;
  });

  const remove = (g: Guest) => run(async () => {
    await removeInvitee(event.id, g.id);
    onChanged();
    return `${g.name} ne fait plus partie des invités`;
  });

  const stop = (l: SentLink) => run(async () => { await stopLink(l.token); return 'Lien arrêté : il ne marche plus'; });

  /** Le même lien, recopié (perdu, ou à renvoyer) : jamais un nouveau lien. */
  const copyLink = (l: SentLink) => run(async () =>
    ((await copyText(inviteLinkUrl(l.token))) ? 'Lien copié' : 'Copie impossible : réessaie'));

  /** Personne invitée par un invité (12.11) : l'organisateur l'accepte (elle voit l'événement) ou la refuse. */
  const decide = (r: JoinRequest, accept: boolean) => run(async () => {
    await decideJoinRequest(event.id, r.id, accept);
    onChanged();
    return accept ? `${r.name} est invité : il voit l’événement` : `${r.name} ne verra pas l’événement`;
  });

  if (!list && loadError && quietOnError) return null;
  if (!list) {
    return (
      <View style={st.card}>
        <T weight="bold" size={20}>Invités</T>
        {loadError ? <ErrorText error={loadError} /> : <Skeleton height={64} radius={radius.md} />}
      </View>
    );
  }

  const counts = guestCounts(list);
  // Vue d'un invité (avis 83ebee37aa0f, 11.11) : les mêmes chiffres, jamais un nom ; ses liens à lui.
  const guest = !!list.guest;
  const waiting = list.people.filter((p) => !p.status && !p.nudged_today);
  const extra = list.people.filter((p) => p.source === 'person' || p.source === 'link' || p.source === 'public');
  const requests = guest ? [] : list.requests ?? [];
  // Sans lien public, la personne invitée par un invité attend l'accord de l'organisateur (12.11).
  const guestRule = list.public ? 'Les personnes que tu invites voient cet événement, rien d’autre.'
    : 'Chaque personne que tu invites attend l’accord de l’organisateur avant de voir l’événement.';

  const row = (g: Guest) => (
    <GuestRow key={g.id} guest={g} me={me.id} onNudge={() => void nudge(g)} onRemove={g.removable ? () => void remove(g) : null} />
  );
  const spoken = linkSpokenNames(list.links);
  const linkRows = (links: SentLink[]) => links.map((l) => (
    <LinkRow key={l.token} link={l} spokenName={spoken.get(l.token) ?? linkTitle(l)} onNudge={guest ? null : () => void nudgeByLink(l)}
      onStop={() => void stop(l)} onCopy={() => void copyLink(l)} />
  ));

  return (
    <View style={st.card} accessibilityLabel="Invités">
      <View style={st.head}>
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="bold" size={20}>Invités · {counts.total}</T>
          <T muted size={13}>{summaryLine(counts, !!list.poll)}</T>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Inviter" onPress={() => setSheet(true)}
          style={({ pressed }) => [st.plus, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
          <T size={26} weight="bold" color={colors.onAction} style={{ lineHeight: 28 }}>+</T>
        </Pressable>
      </View>

      {requests.length ? (
        <View style={st.asking}>
          <T size={15} weight="bold" color={colors.coral}>
            {requests.length > 1 ? `${requests.length} personnes attendent ton accord` : `${requests[0]!.name} attend ton accord`}
          </T>
          <T muted size={12}>Invités par tes invités : ils ne voient l’événement qu’une fois acceptés.</T>
          {requests.map((r) => (
            <RequestRow key={r.id} request={r} me={me.id} onAccept={() => void decide(r, true)} onRefuse={() => void decide(r, false)} />
          ))}
        </View>
      ) : null}

      {counts.total ? (
        <Meter height={6} parts={[
          { fraction: counts.yes / counts.total, color: rsvpColors.yes },
          { fraction: counts.maybe / counts.total, color: rsvpColors.maybe },
          { fraction: counts.no / counts.total, color: rsvpColors.no },
          { fraction: counts.none / counts.total, color: NONE_COLOR },
        ]} />
      ) : null}

      <Pressable accessibilityRole="button" accessibilityState={{ expanded }} aria-expanded={expanded}
        accessibilityLabel={expanded ? 'Réduire la liste des invités' : 'Voir le détail des invités'}
        onPress={() => setExpanded((v) => !v)} hitSlop={6}
        style={({ pressed }) => [st.toggle, pressed && { opacity: 0.7 }]}>
        <T size={14} weight="semibold" color={colors.accent}>{expanded ? 'Réduire' : 'Voir le détail'}</T>
        <T size={16} color={colors.accent} style={{ transform: [{ rotate: expanded ? '-90deg' : '90deg' }] }}>›</T>
      </Pressable>

      <ErrorText error={error} />

      {expanded ? (<>
      <Pressable accessibilityRole="button" onPress={() => setSheet(true)}
        style={({ pressed }) => [st.inviteMore, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
        <T size={15} weight="bold" color={colors.onAction}>＋ Inviter d’autres personnes</T>
      </Pressable>

      <View style={st.rule}>
        <T size={14} weight="bold">{guest ? 'Tu vois les chiffres ; toi aussi, tu peux inviter. ' : ''}{ruleSentence(list)}</T>
        <T muted size={12}>{guest ? guestRule : 'Personne n’est ajouté au groupe : les invités voient cet événement, rien d’autre.'}</T>
      </View>

      <View style={st.tiles} accessibilityRole="tablist" accessibilityLabel="Filtrer les invités">
        {TILES.filter((t) => !list.poll || (t.key !== 'maybe' && t.key !== 'no')).map((t) => {
          const on = filter === t.key;
          const label = list.poll && t.key === 'yes' ? 'Ont voté' : t.label;
          return (
            <Pressable key={t.key} accessibilityRole="tab" accessibilityState={{ selected: on }} aria-selected={on}
              accessibilityLabel={`${counts[t.key]} ${label}`}
              disabled={guest} onPress={() => setFilter(on ? 'all' : t.key)}
              style={({ pressed }) => [st.tile, on && { borderColor: t.color, backgroundColor: colors.surface2 }, pressTransition,
                pressed && { transform: [{ scale: 0.96 }] }]}>
              <T size={22} weight="bold" color={t.color}>{counts[t.key]}</T>
              <T size={12} weight="semibold" color={on ? colors.text : colors.muted} numberOfLines={2} style={{ textAlign: 'center' }}>{label}</T>
            </Pressable>
          );
        })}
      </View>

      {waiting.length && !guest ? (
        <Pressable accessibilityRole="button" onPress={() => void nudgeAll(waiting)}
          style={({ pressed }) => [st.nudgeAll, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
          <T size={14} weight="bold" color={colors.accent}>
            ↻ Relancer {waiting.length > 1 ? `les ${waiting.length} qui n’ont pas répondu` : `${waiting[0]!.name}, sans réponse`}
          </T>
        </Pressable>
      ) : null}

      {guest ? (
        <View style={{ gap: 14 }}>
          {list.links.length ? <Block title={`Mes liens · ${list.links.length}`}>{linkRows(list.links)}</Block> : (
            <T muted size={14}>Touche « + » pour envoyer ton propre lien : tu verras combien de personnes y répondent.</T>
          )}
        </View>
      ) : filter === 'all' ? (
        <View style={{ gap: 14 }}>
          {groupBlocks(list).map((b) => (
            <GroupBlock key={b.name} name={b.name} people={b.people} open={open.has(b.name)}
              onToggle={() => setOpen((prev) => { const next = new Set(prev); if (next.has(b.name)) next.delete(b.name); else next.add(b.name); return next; })}>
              {b.people.map(row)}
            </GroupBlock>
          ))}
          {extra.length ? <Block title={`En plus · ${extra.length}`} hint="Hors du groupe">{extra.map(row)}</Block> : null}
          {list.links.length ? <Block title={`Liens envoyés · ${list.links.length}`}>{linkRows(list.links)}</Block> : null}
          {!list.people.length && !list.links.length ? (
            <T muted size={14}>Personne pour l’instant. Touche « + » pour envoyer le lien ou ajouter des gens de Party.</T>
          ) : null}
        </View>
      ) : (
        <View style={{ gap: 6 }}>
          {filterGuests(list, filter).map(row)}
          {linkRows(filterLinks(list, filter))}
          {!filterGuests(list, filter).length && !filterLinks(list, filter).length ? <T muted size={14}>Personne ici.</T> : null}
        </View>
      )}
      </>) : null}

      <InviteSheet visible={sheet} event={event} me={me} list={list} onClose={() => setSheet(false)} onInvited={refresh} guest={guest}
        headline={headline} initialPeople={initialPeople} />
      {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
    </View>
  );
}

/** L'essentiel en une ligne (carte repliée) : les chiffres non nuls seulement. */
function summaryLine(c: ReturnType<typeof guestCounts>, poll: boolean): string {
  const none = c.none + c.unopened;
  const parts = poll
    ? [`${c.yes} ${c.yes > 1 ? 'ont voté les dates' : 'a voté les dates'}`]
    : [`${c.yes} ${c.yes > 1 ? 'viennent' : 'vient'}`, c.maybe ? `${c.maybe} peut-être` : null,
       c.no ? `${c.no} ${c.no > 1 ? 'absents' : 'absent'}` : null];
  return [...parts, none ? `${none} sans réponse` : null].filter(Boolean).join(' · ');
}

/** Le groupe Vendredi Party et les groupes invités, repliés en une ligne chacun. */
function groupBlocks(list: GuestList): { name: string; people: Guest[] }[] {
  const names = [...(list.vip ? [list.vip_name || 'Vendredi Party'] : []), ...list.groups.map((g) => g.name)];
  return names.map((name) => ({
    name,
    people: list.people.filter((p) => (p.source === 'vip' || p.source === 'group') && (p.group ?? '').split(', ').includes(name)),
  }));
}

function Block({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <View style={{ gap: 6 }}>
      <View style={[st.rowCenter, { gap: 6 }]}>
        <T size={12} weight="bold" color={colors.muted}>{title.toUpperCase()}</T>
        {hint ? <T size={12} muted>· {hint}</T> : null}
      </View>
      {children}
    </View>
  );
}

function GroupBlock({ name, people, open, onToggle, children }: { name: string; people: Guest[]; open: boolean; onToggle: () => void; children: ReactNode }) {
  const yes = people.filter((p) => p.status === 'yes').length;
  const maybe = people.filter((p) => p.status === 'maybe').length;
  const none = people.filter((p) => !p.status).length;
  const answered = people[0]?.poll ? `${yes} ${yes > 1 ? 'ont voté' : 'a voté'}` : `${yes} ${yes > 1 ? 'viennent' : 'vient'}`;
  return (
    <View style={{ gap: 6 }}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`Groupe ${name}, ${people.length} personnes`}
        onPress={onToggle} style={({ pressed }) => [st.groupRow, pressed && { opacity: 0.8 }]}>
        <View style={st.groupIcon}><T size={18}>👥</T></View>
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="bold" size={15} numberOfLines={1}>{name} · {people.length}</T>
          <T muted size={12} numberOfLines={1}>{answered}{maybe ? ` · ${maybe} peut-être` : ''}{none ? ` · ${none} sans réponse` : ''}</T>
        </View>
        <T size={18} color={colors.muted} style={{ transform: [{ rotate: open ? '90deg' : '0deg' }] }}>›</T>
      </Pressable>
      {open ? <View style={{ gap: 6 }}>{children}</View> : null}
    </View>
  );
}

function StatusPill({ guest }: { guest: Guest }) {
  const label = guest.poll ? (guest.status ? 'A voté' : 'Pas voté')
    : guest.status === 'yes' && guest.waitlisted ? 'En attente' : guest.status ? statusWords[guest.status] : 'Pas répondu';
  const color = guest.status ? rsvpColors[guest.status] : NONE_COLOR;
  return (
    <View style={[st.pill, { borderColor: color }]}>
      <View style={[st.dot, { backgroundColor: color }]} />
      <T size={12} weight="bold" color={color}>{label}{guest.plus_ones ? ` +${guest.plus_ones}` : ''}</T>
    </View>
  );
}

function GuestRow({ guest, me, onNudge, onRemove }: { guest: Guest; me: string; onNudge: () => void; onRemove: (() => void) | null }) {
  const [confirm, setConfirm] = useState(false);
  const canNudge = !guest.status && !guest.nudged_today;
  // « Relancer » est déjà sur la ligne ; le glissé montre « Retirer » (en deux temps).
  const actions = onRemove ? [{ label: confirm ? 'Confirmer' : 'Retirer', color: colors.red, fg: colors.onRed,
    onPress: () => (confirm ? onRemove() : setConfirm(true)) }] : [];
  return (
    <SwipeRow actions={actions} label={guest.name}>
      <View style={st.row}>
        <Avatar id={guest.id} name={guest.name} photo={guest.avatar_url} size={40} profile={false} />
        <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
          <View style={[st.rowCenter, { gap: 6 }]}>
            <T weight="semibold" size={15} numberOfLines={1} style={{ flexShrink: 1 }}>{guest.name}</T>
            {guest.light ? <View style={st.tag}><T size={10} weight="bold" color={colors.muted}>SANS L’APP</T></View> : null}
          </View>
          <T muted size={12} numberOfLines={1}>{guestOrigin(guest, me)}</T>
        </View>
        {canNudge ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Relancer ${guest.name}`} hitSlop={6} onPress={onNudge}
            style={({ pressed }) => [st.smallAction, pressed && { opacity: 0.7 }]}>
            <T size={12} weight="bold" color={colors.accent}>Relancer</T>
          </Pressable>
        ) : !guest.status && guest.nudged_today ? <T size={11} muted>Relancé ✓</T> : <StatusPill guest={guest} />}
      </View>
    </SwipeRow>
  );
}

const ANSWER_WORDS = { yes: 'Viendrait', maybe: 'Peut-être', no: 'Ne peut pas', poll: 'Votera les dates' } as const;

/** Une demande : qui, invité par qui, sa réponse ; Accepter (il voit l'événement) ou Refuser (en deux temps). */
function RequestRow({ request, me, onAccept, onRefuse }: { request: JoinRequest; me: string; onAccept: () => void; onRefuse: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const by = request.invited_by_id === me ? 'toi' : request.invited_by?.trim() || 'un invité';
  const origin = `Invité par ${by}${request.link_label ? ` · lien « ${request.link_label} »` : ''}`;
  return (
    <View style={[st.row, st.request]} accessibilityLabel={`${request.name}, ${origin}, attend ton accord`}>
      <Avatar id={request.id} name={request.name} photo={request.avatar_url} size={40} profile={false} />
      <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
        <T weight="semibold" size={15} numberOfLines={1}>{request.name}</T>
        <T muted size={12} numberOfLines={2}>{origin} · {ANSWER_WORDS[request.answer]}</T>
      </View>
      <View style={{ gap: 6 }}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Accepter ${request.name}`} hitSlop={4} onPress={onAccept}
          style={({ pressed }) => [st.accept, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
          <T size={13} weight="bold" color={colors.onAction}>Accepter</T>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={confirm ? `Confirmer le refus de ${request.name}` : `Refuser ${request.name}`}
          hitSlop={4} onPress={() => (confirm ? onRefuse() : setConfirm(true))}
          style={({ pressed }) => [st.refuse, pressed && { opacity: 0.7 }]}>
          <T size={13} weight="bold" color={colors.red}>{confirm ? 'Confirmer' : 'Refuser'}</T>
        </Pressable>
      </View>
    </View>
  );
}

function LinkRow({ link, spokenName, onNudge, onStop, onCopy }: {
  link: SentLink; spokenName: string; onNudge: (() => void) | null; onStop: () => void; onCopy: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  // Un lien « Plusieurs » sans limite reste « ouvert » après des réponses : il se recopie tant qu'il marche.
  const live = link.state === 'pending' || link.state === 'opened' || (link.max_uses > 1 && link.uses < link.max_uses
    && link.state !== 'expired' && link.state !== 'revoked');
  const arrivalNames = link.arrivals.map((a) => a.name).filter(Boolean).join(', ');
  const title = linkTitle(link);
  const asking = link.arrivals.filter((a) => a.request === 'pending').length;
  const badge = asking && link.max_uses === 1 ? { t: 'En attente', c: colors.coral }
    : link.state === 'opened' && !link.arrivals.length ? { t: 'A ouvert', c: colors.coral }
    : link.state === 'pending' ? { t: 'Pas ouvert', c: UNOPENED_COLOR }
      : link.arrivals.length ? { t: unlimited(link.max_uses) ? `${link.uses} ✓` : link.max_uses > 1 ? `${link.uses}/${link.max_uses}` : 'Répondu', c: rsvpColors.yes }
        : { t: link.state === 'revoked' ? 'Arrêté' : 'Terminé', c: colors.muted };
  const actions = live ? [
    ...(link.nudged_today || !onNudge ? [] : [{ label: '↻ Relancer', color: colors.lavender, fg: colors.bg, onPress: onNudge }]),
    { label: confirm ? 'Confirmer' : 'Arrêter', color: colors.red, fg: colors.onRed, onPress: () => (confirm ? onStop() : setConfirm(true)) },
  ] : [];
  return (
    <SwipeRow actions={actions} label={spokenName}>
      <View style={st.row}>
        <View style={st.linkIcon}><T size={17}>{link.max_uses > 1 ? '👥' : '🔗'}</T></View>
        <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
          <T weight="semibold" size={15} numberOfLines={1}>{title}</T>
          <T muted size={12} numberOfLines={2}>{linkLine(link)}{link.max_uses > 1 && arrivalNames ? ` · ${arrivalNames}` : ''}</T>
        </View>
        <View style={[st.pill, { borderColor: badge.c }]}><T size={12} weight="bold" color={badge.c}>{badge.t}</T></View>
        {live ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Copier le lien : ${spokenName}`} onPress={onCopy} hitSlop={8}
            style={({ pressed }) => [st.copy, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
            <T size={13} weight="bold" color={colors.accent}>Copier</T>
          </Pressable>
        ) : null}
      </View>
    </SwipeRow>
  );
}

type SwipeAction = { label: string; color: string; fg: string; onPress: () => void };

/** Lignes ouvertes (une seule à la fois) : chacune se ferme quand une autre s'ouvre ou quand la page défile. */
const openRows = new Set<() => void>();
let pageScrollWatched = false;

function watchPageScroll() {
  if (pageScrollWatched || typeof document === 'undefined') return;
  pageScrollWatched = true;
  // Défilement de la page (pas d'une ligne) : toute ligne ouverte se referme, comme Mail sur iPhone.
  document.addEventListener('scroll', (e) => {
    const target = e.target as Element | null;
    if (target?.closest?.('[data-testid="swipe-row"]')) return;  // le glissé d'une ligne n'est pas un défilement de la page
    openRows.forEach((close) => close());
  }, { capture: true, passive: true });
}

/** Fin du geste : ouverte si on a tiré au-delà de la moitié des actions, sinon fermée (jamais entre les deux). */
const SETTLE_MS = 140;
const CLOSE_MS = 600;  // durée max. du retour animé d'une ligne

/** Ligne qui glisse vers la gauche pour montrer ses actions (comme Mail sur iPhone). Défilement horizontal natif du
 * navigateur : le doigt qui monte ou descend fait toujours défiler la page. Une seule ligne ouverte, refermée par le
 * défilement de la page (retour de l'admin, 08.11 : des lignes montraient « Retirer » toutes seules). */
function SwipeRow({ actions, label, children }: { actions: SwipeAction[]; label: string; children: ReactNode }) {
  const [width, setWidth] = useState(0);
  const scroller = useRef<ScrollView>(null);
  const settle = useRef<ReturnType<typeof setTimeout> | null>(null);
  const full = actions.length * ACTION_WIDTH;
  const closing = useRef(false);  // retour à 0 en cours : ce défilement n'est pas une ouverture
  const close = useMemo(() => {
    const fn = () => {
      openRows.delete(fn);
      closing.current = true;
      setTimeout(() => { closing.current = false; }, CLOSE_MS);  // jamais bloquée si le retour n'arrive pas à 0
      scroller.current?.scrollTo({ x: 0, animated: true });
    };
    return fn;
  }, []);
  useEffect(() => {
    watchPageScroll();
    return () => { openRows.delete(close); if (settle.current) clearTimeout(settle.current); };
  }, [close]);
  const content = useMemo(() => <View style={[st.rowShell, width ? { width } : null]}>{children}</View>, [children, width]);
  if (!actions.length) return <View style={st.rowShell}>{children}</View>;

  function onScroll(x: number) {
    if (closing.current) {
      if (x <= 0) closing.current = false;
      return;
    }
    if (x > 4) {
      openRows.forEach((other) => { if (other !== close) other(); });
      openRows.add(close);
    }
    if (settle.current) clearTimeout(settle.current);
    settle.current = setTimeout(() => {
      const open = x > full / 2;
      if (!open) openRows.delete(close);
      if (x > 0 && x < full) scroller.current?.scrollTo({ x: open ? full : 0, animated: true });
    }, SETTLE_MS);
  }

  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)} style={st.swipe}>
      <ScrollView ref={scroller} testID="swipe-row" horizontal showsHorizontalScrollIndicator={false} bounces={false} scrollEventThrottle={16}
        onScroll={(e) => onScroll(e.nativeEvent.contentOffset.x)}>
        {content}
        <View style={[st.swipeActions, { width: full }]}>
          {actions.map((a) => (
            <Pressable key={a.label} accessibilityRole="button" accessibilityLabel={`${a.label.replace('↻ ', '')} ${label}`} onPress={a.onPress}
              style={[st.swipeAction, { backgroundColor: a.color }]}>
              <T size={13} weight="bold" color={a.fg}>{a.label}</T>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  inviteMore: { minHeight: 48, borderRadius: radius.md, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, padding: 16, gap: 12 },
  toggle: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', gap: 6, minHeight: 32 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  plus: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
  rule: { gap: 2, padding: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tile: { flexGrow: 1, flexBasis: '30%', minHeight: 64, paddingVertical: 8, paddingHorizontal: 8, borderRadius: radius.md,
    borderWidth: 1.5, borderColor: 'transparent', backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center', gap: 2 },
  nudgeAll: { minHeight: 44, borderRadius: radius.md, borderWidth: 1, borderColor: colors.accent, borderStyle: 'dashed',
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  rowCenter: { flexDirection: 'row', alignItems: 'center' },
  groupRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: radius.md, backgroundColor: colors.surface2 },
  groupIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.lavenderDim, alignItems: 'center', justifyContent: 'center' },
  swipe: { borderRadius: radius.md, overflow: 'hidden' },
  rowShell: { backgroundColor: colors.surface, borderRadius: radius.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 6, paddingHorizontal: 4 },
  // Hauteur de la ligne, jamais moins de 44 px (« Confirmer » s'écrasait à 16 px, texte coupé : campagne des bots).
  swipeActions: { flexDirection: 'row', alignSelf: 'stretch', minHeight: 56 },
  swipeAction: { width: ACTION_WIDTH, minHeight: 56, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, paddingVertical: 4, borderRadius: radius.pill, borderWidth: 1 },
  copy: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.surface2 },
  request: { borderRadius: radius.md, padding: 10, backgroundColor: colors.surface2 },
  asking: { gap: 8, padding: 12, borderRadius: radius.lg, borderWidth: 1.5, borderColor: colors.coral },
  accept: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.pill, backgroundColor: colors.action, alignItems: 'center' },
  refuse: { paddingHorizontal: 12, paddingVertical: 5, alignItems: 'center' },
  dot: { width: 7, height: 7, borderRadius: 4 },
  tag: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, backgroundColor: colors.fillStrong },
  smallAction: { minHeight: 32, paddingHorizontal: 12, borderRadius: radius.pill, backgroundColor: colors.accentDim, alignItems: 'center', justifyContent: 'center' },
  linkIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.fillStrong, alignItems: 'center', justifyContent: 'center' },
});
