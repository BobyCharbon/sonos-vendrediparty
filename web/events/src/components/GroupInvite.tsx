import { useRef, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { GroupTile } from './GroupBits';
import { inviteUrl } from './InviteLinkCard';
import { usePersonText } from './PersonName';
import { Avatar, Button, ErrorText, Input, T, Toast } from './ui';
import { useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { plural } from '@/lib/format';
import { fetchSuggestions, type GroupLook, type GroupSuggestion } from '@/lib/groups';
import { copyText, openWhatsApp, shareInvite } from '@/lib/invites';
import { enter, pressTransition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { qrDataUri } from '@/lib/tickets';
import { colors, font, radius } from '@/lib/theme';

type Picked = { id: string | null; name: string; phone?: string };

/** Numéro tapé (« 079 123 45 67 », « +41 79… ») → chiffres au format international, comme l'ancien écran Groupes. */
function phoneOf(typed: string): string | null {
  const digits = typed.replace(/\D/g, '');
  if (!/^[+0-9][0-9 .()-]{6,}$/.test(typed.trim()) || digits.length < 8) return null;
  return digits.startsWith('0') && digits.length === 10 ? `41${digits.slice(1)}` : digits;
}

/** « Chloé, Malik et Inès », « Chloé, Malik et 3 autres ». */
export function namesLine(names: string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  if (names.length <= 3) return `${names.slice(0, -1).join(', ')} et ${names[names.length - 1]}`;
  return `${names.slice(0, 2).join(', ')} et ${names.length - 2} autres`;
}

/**
 * Inviter dans un groupe (étape 2 de la création, et « Inviter » de la page du groupe) : le lien du groupe
 * (WhatsApp / Copier / Autre) et son code QR, puis « Déjà sur Party » : seulement des personnes déjà croisées à un
 * événement (group_invite_suggestions, jamais tout le site), un surnom exact ou un numéro. Chacun reçoit une
 * invitation (invite_to_group) et entre dès qu'il accepte. Droits de la base inchangés (créateur, Admin du site).
 */
export function GroupInvitePanel({ group, fresh = false, onInvited }: {
  group: GroupLook; fresh?: boolean; onInvited?: (count: number) => void;
}) {
  const me = useMe();
  const personText = usePersonText();
  const [search, setSearch] = useState('');
  const [picked, setPicked] = useState<Picked[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [sent, setSent] = useState<Set<string>>(new Set());
  const inviting = useRef(false);

  const { data: url, error: linkError } = useQuery(async () => {
    const { data, error: failed } = await supabase.rpc('group_invite_link', { grp: group.id, renew: false });
    if (failed || !data) throw new Error('Le lien n’a pas pu être créé. Réessaie.');
    return inviteUrl('group', data as string);
  }, [group.id]);
  const { data: people, error: peopleError } = useQuery(() => fetchSuggestions(group.id), [group.id]);

  const host = me.display_name.trim() || 'Moi';
  const message = (link: string) => `Hello ! ${host} t’invite dans le groupe « ${group.emoji} ${group.name} » sur Party. Rejoins-le ici : ${link}`;
  const name = (p: GroupSuggestion) => personText(p.id, p.display_name);
  const q = search.trim().toLocaleLowerCase('fr').replace(/^@/, '');
  const phone = phoneOf(search);
  const shown = (people ?? []).filter((p) => !q || phone || name(p).toLocaleLowerCase('fr').includes(q) || p.display_name.toLocaleLowerCase('fr').includes(q));
  const isPicked = (id: string) => picked.some((p) => p.id === id);

  function toggle(p: GroupSuggestion) {
    setPicked(isPicked(p.id) ? picked.filter((x) => x.id !== p.id) : [...picked, { id: p.id, name: name(p) }]);
  }

  async function send(how: 'whatsapp' | 'copy' | 'other') {
    if (!url) return;
    if (how === 'whatsapp') openWhatsApp(message(url));
    else if (how === 'copy') setNote((await copyText(url)) ? 'Lien copié' : 'Copie impossible : touche le lien pour le sélectionner');
    else if ((await shareInvite(message(url), url, group.name)) === 'copied') setNote('Message copié : colle-le où tu veux');
  }

  /** Surnom exact (compte existant) ou numéro (inscrit ou pas : l'invitation l'attend), comme l'ancien écran. */
  async function addTyped() {
    const typed = search.trim().replace(/^@/, '');
    if (!typed) return;
    if (phone) {
      setPicked([...picked, { id: null, name: search.trim(), phone }]);
      return setSearch('');
    }
    const { data } = await supabase.from('profiles').select('id, display_name').eq('status', 'active')
      .ilike('display_name', typed.replace(/[\\%_]/g, (c) => `\\${c}`)).limit(1);
    const found = (data ?? [])[0] as { id: string; display_name: string } | undefined;
    if (!found || found.id === me.id) return setError('Personne avec ce surnom. Essaie son numéro de téléphone.');
    setError(null);
    if (!isPicked(found.id)) setPicked([...picked, { id: found.id, name: personText(found.id, found.display_name) }]);
    setSearch('');
  }

  async function invite() {
    if (inviting.current || !picked.length) return;
    inviting.current = true;
    setBusy(true);
    setError(null);
    const done: Picked[] = [];
    try {
      for (const p of picked) {
        const { error: failed } = await supabase.rpc('invite_to_group', { grp: group.id, member: p.id, phone: p.phone ?? null });
        if (failed) throw new Error(`${p.name} : ${failed.message.replace(/^\w+: /, '')}`);
        done.push(p);
      }
      setNote(`${namesLine(done.map((p) => p.name))} : invitation envoyée`);
      setSearch('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'L’invitation n’a pas pu partir. Réessaie.');
    } finally {
      setSent((s) => new Set([...s, ...done.map((p) => p.id ?? p.phone ?? '')]));
      setPicked((list) => list.filter((p) => !done.includes(p)));
      inviting.current = false;
      setBusy(false);
      if (done.length) onInvited?.(done.length);
    }
  }

  return (
    <View style={{ gap: 18 }} testID="group-invite-panel">
      <View style={[st.head, enter('rise')]}>
        <GroupTile group={group} size={52} />
        <View style={{ flex: 1 }}>
          <Text role="heading" style={st.title}>{fresh ? 'Invite ta bande' : 'Inviter dans le groupe'}</Text>
          <T muted size={14}>{fresh ? `« ${group.name} » est prêt. Invite maintenant ou plus tard.` : `« ${group.name} » : envoie le lien ou choisis des gens déjà croisés.`}</T>
        </View>
      </View>

      {/* Le lien du groupe et son code QR (direction B) : qui l'ouvre rejoint le groupe. */}
      <View style={[st.linkCard, enter('rise', 1)]}>
        <T weight="bold" size={16}>🔗 Le lien du groupe</T>
        <T size={13} color={colors.textSoft}>Qui l’ouvre rejoint le groupe (avec son numéro s’il n’a pas encore de compte). Tu es prévenu à chaque arrivée.</T>
        <View style={st.urlBox}>
          {url ? <T size={14} weight="semibold" numberOfLines={1} style={st.mono}>{url.replace(/^https?:\/\//, '')}</T>
            : linkError ? <ErrorText error={linkError} /> : <T muted size={13}>Préparation du lien…</T>}
        </View>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {([['whatsapp', '💬', 'WhatsApp'], ['copy', '⧉', 'Copier'], ['other', '⇪', 'Autre']] as const).map(([k, icon, l]) => (
            <Pressable key={k} accessibilityRole="button" accessibilityLabel={l} disabled={!url} onPress={() => void send(k)}
              style={({ pressed }) => [st.shareBtn, k === 'whatsapp' && st.whatsapp, !url && { opacity: 0.5 }, pressTransition,
                pressed && { transform: [{ scale: 0.95 }] }]}>
              <T size={15}>{icon}</T>
              <T size={14} weight="bold" color={k === 'whatsapp' ? '#FFFFFF' : colors.text}>{l}</T>
            </Pressable>
          ))}
        </View>
        {url ? (
          <View style={st.qrRow}>
            <Image source={{ uri: qrDataUri(url) }} style={st.qr} accessibilityLabel="Code QR du lien du groupe" />
            <View style={{ flex: 1, gap: 4 }}>
              <T weight="bold" size={16}>Montre ce code</T>
              <T muted size={13}>La personne le vise avec l’appareil photo, s’inscrit et rejoint le groupe.</T>
            </View>
          </View>
        ) : null}
      </View>

      <View style={{ gap: 10 }}>
        <T size={13} weight="bold" color={colors.muted} style={st.label}>DÉJÀ SUR PARTY</T>
        <Input accessibilityLabel="Chercher une personne" placeholder="🔍 Prénom, surnom ou numéro" value={search}
          onChangeText={(v) => { setSearch(v); setError(null); }} onSubmitEditing={() => void addTyped()} />
        {phone ? (
          <Button small variant="secondary" label={`Inviter le numéro ${search.trim()}`} onPress={() => void addTyped()} />
        ) : q && !shown.length ? (
          <Button small variant="secondary" label={`Inviter le surnom « ${search.trim()} »`} onPress={() => void addTyped()} />
        ) : null}
        {picked.filter((p) => !p.id).map((p) => (
          <View key={p.phone} style={st.person}>
            <View style={[st.phoneDot]}><T size={16}>📱</T></View>
            <T weight="semibold" style={{ flex: 1 }}>{p.name}</T>
            <Pressable accessibilityRole="button" accessibilityLabel={`Retirer ${p.name}`} onPress={() => setPicked(picked.filter((x) => x !== p))}>
              <View style={[st.check, st.checkOn]}><T size={13} weight="bold" color={colors.onAction}>✓</T></View>
            </Pressable>
          </View>
        ))}
        {people && !people.length && !q ? (
          <T muted size={13}>Personne croisée à un événement pour l’instant : envoie le lien du groupe, ou tape un surnom ou un numéro.</T>
        ) : null}
        <ErrorText error={peopleError} />
        <View>
          {shown.slice(0, 30).map((p, i) => {
            const on = isPicked(p.id);
            const done = p.invited || sent.has(p.id);
            return (
              <Pressable key={p.id} accessibilityRole="checkbox" accessibilityState={{ checked: on, disabled: done }} aria-checked={on}
                accessibilityLabel={`${done ? 'Déjà invité : ' : on ? 'Retirer ' : 'Ajouter '}${name(p)}`} disabled={done} onPress={() => toggle(p)}
                style={({ pressed }) => [st.person, i ? st.personLine : null, pressTransition, pressed && { opacity: 0.7 }]}>
                <Avatar id={p.id} name={p.display_name} photo={p.avatar_url} size={40} profile={false} />
                <View style={{ flex: 1, minWidth: 0 }}>
                  <T weight="semibold" numberOfLines={1}>{name(p)}</T>
                  <T muted size={13} numberOfLines={1}>
                    {done ? 'Invitation envoyée' : p.together > 1 ? `${plural(p.together, 'soirée')} ensemble` : p.last_title ?? 'Croisé à un événement'}
                  </T>
                </View>
                <View key={on ? 'on' : 'off'} style={[st.check, (on || done) && st.checkOn, done && { opacity: 0.5 }, on && enter('pop')]}>
                  {on || done ? <T size={13} weight="bold" color={colors.onAction}>✓</T> : null}
                </View>
              </Pressable>
            );
          })}
        </View>
        {picked.length ? (
          <View style={enter('rise')}>
            <Button label={`Inviter ${namesLine(picked.map((p) => p.name))}`} loading={busy} onPress={() => void invite()} />
          </View>
        ) : null}
        <ErrorText error={error} />
        <T muted size={13} style={{ textAlign: 'center' }}>Ils reçoivent une invitation et entrent dans le groupe d’un toucher.</T>
      </View>
      {note ? <Toast message={note} onHide={() => setNote(null)} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  title: { color: colors.text, fontSize: 24, ...font.display, letterSpacing: -0.4 },
  label: { letterSpacing: 0.8 },
  linkCard: { gap: 12, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  urlBox: { minHeight: 46, justifyContent: 'center', paddingHorizontal: 14, borderRadius: radius.md, backgroundColor: 'rgba(0,0,0,0.25)' },
  mono: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' },
  shareBtn: { flex: 1, flexDirection: 'row', gap: 6, minHeight: 48, borderRadius: radius.md, backgroundColor: colors.fillStrong,
    alignItems: 'center', justifyContent: 'center' },
  whatsapp: { backgroundColor: '#1FA855' },
  qrRow: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface2 },
  qr: { width: 112, height: 112, borderRadius: 12 },
  person: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, paddingVertical: 8 },
  personLine: { borderTopWidth: 1, borderTopColor: colors.line },
  phoneDot: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.lavenderDim, alignItems: 'center', justifyContent: 'center' },
  check: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  checkOn: { backgroundColor: colors.accent, borderColor: colors.accent },
});
