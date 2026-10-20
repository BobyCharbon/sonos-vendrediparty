import { Redirect } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Announcements } from '@/components/Announcements';
import { Button, ErrorText, Field, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

export default function AdminAnnouncements() {
  const { can } = useAuth();
  const isAdmin = can('announcements.publish');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [published, setPublished] = useState(false);
  const [version, setVersion] = useState(0);
  if (!isAdmin) return <Redirect href="/" />;

  async function publish() {
    if (lock.current || !title.trim() || !body.trim()) return;
    lock.current = true; setBusy(true); setError(null); setPublished(false);
    try {
      must(await supabase.rpc('publish_admin_announcement', { announcement_title: title.trim(), announcement_body: body.trim() }));
      setTitle(''); setBody(''); setPublished(true); setVersion((v) => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : 'L’annonce n’a pas été publiée. Réessaie.'); }
    finally { lock.current = false; setBusy(false); }
  }

  return (
    <Screen edges={[]}>
      <Title>Publier une annonce</Title>
      <T muted>Visible pour tous les membres, sans désabonnement possible. Elle restera dans Activité. Les appareils autorisés seront prévenus, en respectant les heures silencieuses.</T>
      <ErrorText error={error} />
      {published ? <View accessibilityRole="alert"><T>L’annonce est publiée pour tout le groupe.</T></View> : null}
      <Field label="Titre" placeholder="L’essentiel en quelques mots" value={title} onChangeText={setTitle} maxLength={120} editable={!busy} />
      <Field label="Message" placeholder="Les informations à communiquer au groupe" multiline value={body} onChangeText={setBody} maxLength={4000} editable={!busy} />
      {title.trim() || body.trim() ? (
        <View style={{ gap: 8, paddingVertical: 16, borderTopWidth: 1, borderTopColor: colors.line }}>
          <T muted size={12}>Aperçu de l’annonce</T><T weight="bold" size={18}>{title.trim()}</T><T>{body.trim()}</T>
        </View>
      ) : null}
      <Button label="Publier pour tout le groupe" disabled={!title.trim() || !body.trim()} loading={busy} onPress={publish} />
      <View style={{ height: 12 }} />
      <Announcements key={version} compact />
    </Screen>
  );
}
