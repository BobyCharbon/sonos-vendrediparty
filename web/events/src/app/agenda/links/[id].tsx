import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ast, StatusPill, TopBar } from '@/components/agenda/Bits';
import { copyText, LinkEditor, QrModal, shareLink } from '@/components/agenda/LinkEditor';
import { Button, ConfirmButton, ErrorText, Screen, T, Toast } from '@/components/ui';
import { dateShort, errorText, linkUrl, rpc, type Links } from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { enter } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';

/** Un lien de dispo : son adresse (Copier, Partager, Code QR), son état, puis tous ses réglages ; Arrêter, Supprimer. */
export default function LinkScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ id: string; created?: string }>();
  const { data, error, loading, reload } = useQuery(async () => (await rpc<Links>('agenda_links')).links.find((l) => l.id === p.id) ?? null, [p.id]);
  useSignal([`user:${me.id}`], reload);
  const [toast, setToast] = useState<string | null>(p.created ? 'Lien créé.' : null);
  const [qr, setQr] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const link = data;

  async function act(action: 'stop' | 'restart' | 'extend' | 'delete') {
    setErr(null);
    try {
      await rpc('agenda_link_set', { id: p.id, action });
      if (action === 'delete') { router.replace('/agenda/links' as Href); return; }
      setToast(action === 'stop' ? 'Lien arrêté. Il n’affiche plus rien.' : action === 'restart' ? 'Lien rallumé, à la même adresse.' : 'Prolongé de 90 jours.');
      await reload();
    } catch (e) { setErr(errorText(e)); }
  }

  return (
    <Screen>
      <TopBar back="Mes liens" fallback="/agenda/links" title={link?.name ?? 'Lien'} titleRight={link ? <StatusPill status={link.status} /> : null} />
      <ErrorText error={error ?? err} />
      {!loading && !data && !error ? <T muted>Ce lien n’existe plus.</T> : null}
      {link ? (
        <>
          <View style={[ast.neonCard, enter('pop')]} testID="link-address">
            <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>ADRESSE DU LIEN</T>
            <T size={14} weight="semibold" numberOfLines={2}>{linkUrl(link)}</T>
            {link.status === 'active' ? (
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button small variant="secondary" label="Copier" style={{ flex: 1 }} onPress={async () => setToast((await copyText(linkUrl(link))) ? 'Lien copié.' : linkUrl(link))} />
                <Button small variant="secondary" label="Partager" style={{ flex: 1 }} onPress={async () => { if ((await shareLink(link)) === 'copied') setToast('Lien copié.'); }} />
                <Button small variant="secondary" label="Code QR" style={{ flex: 1 }} onPress={() => setQr(true)} />
              </View>
            ) : <T muted size={13}>Le lien n’affiche plus rien. Rallumé, il garde la même adresse.</T>}
            <T muted size={13}>{link.views ? `Vu ${link.views} fois` : 'Pas encore vu'} · {link.status === 'active' ? (link.expires_at ? `s’arrête seul le ${dateShort(link.expires_at)}` : 'permanent') : link.status === 'stopped' ? 'arrêté' : 'expiré'}</T>
          </View>
          {link.status === 'active' ? (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {link.expires_at ? <Button small variant="secondary" label="Prolonger de 90 jours" style={{ flex: 1 }} onPress={() => void act('extend')} /> : null}
              <Button small variant="danger" label="Arrêter" style={{ flex: 1 }} onPress={() => void act('stop')} />
            </View>
          ) : <Button label="Rallumer ce lien" onPress={() => void act('restart')} />}
          {link.booking_enabled || link.pending ? (
            <Button variant="secondary" label={link.pending ? `📩 ${link.pending} demande${link.pending > 1 ? 's' : ''} de rendez-vous` : '📩 Demandes reçues'}
              onPress={() => router.push(`/agenda/requests?link=${link.id}` as Href)} />
          ) : null}
          <View style={st.sep} />
          <LinkEditor key={link.id} link={link} onSaved={() => { setToast('Lien enregistré.'); void reload(); }} />
          <ConfirmButton label="Supprimer ce lien" confirmLabel="Supprimer" onConfirm={() => act('delete')} />
          <T muted size={12}>Les rendez-vous déjà acceptés restent dans ton agenda ; les demandes en attente partent avec le lien.</T>
          <QrModal link={qr ? link : null} onClose={() => setQr(false)} />
        </>
      ) : null}
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </Screen>
  );
}

const st = StyleSheet.create({
  sep: { height: 1, backgroundColor: colors.line, marginVertical: 4, borderRadius: radius.pill },
});

