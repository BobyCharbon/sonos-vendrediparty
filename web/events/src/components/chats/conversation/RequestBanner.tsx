import { useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { C, cf, Icon, pinkButton, web } from './kit';
import { Avatar } from '../../ui';
import { enter, pressTransition } from '@/lib/motion';

type Incoming = {
  side: 'incoming';
  name: string; userId: string; photo: string | null;
  onAccept: () => Promise<void>;
  onDelete: () => Promise<void>;
  onBlock: () => Promise<void>;
  onReport: () => void;
  onProfile: () => void;
};
type Outgoing = { side: 'outgoing'; name: string; sent: boolean };

/** Demande de message (contrat §2, conformité C2) : chez le destinataire « X veut t'écrire » + Accepter / Supprimer /
 * Bloquer / Signaler, sans « Vu » ni « écrit… » ; chez l'expéditeur « Demande envoyée » (jamais prévenu d'un refus). */
export function RequestBanner(props: Incoming | Outgoing) {
  if (props.side === 'outgoing') {
    return (
      <View accessibilityRole="summary" style={[card, enter('drop')]}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Icon name="lock" size={18} color={C.lav} />
          <Text accessibilityRole="header" style={[cf.display, { color: C.t1, fontSize: 18 }]}>Demande envoyée</Text>
        </View>
        <Text style={[cf.text, { color: C.t2, fontSize: 14, lineHeight: 20 }]}>
          {props.sent
            ? `${props.name} verra ton message dans ses demandes. Tu pourras continuer la discussion quand ta demande sera acceptée.`
            : `Vous n’avez pas encore de lien direct : ton premier message sera une demande. Un seul message texte, sans photo, vocal, lien ni numéro.`}
        </Text>
      </View>
    );
  }
  return <IncomingBanner {...props} />;
}

function IncomingBanner({ name, userId, photo, onAccept, onDelete, onBlock, onReport, onProfile }: Incoming) {
  const [busy, setBusy] = useState<'accept' | 'delete' | 'block' | null>(null);
  const [confirmBlock, setConfirmBlock] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const act = (kind: 'accept' | 'delete' | 'block', f: () => Promise<void>) => async () => {
    if (busy) return;
    setBusy(kind);
    setError(null);
    try {
      await f();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ça n’a pas marché. Réessaie.');
    } finally {
      setBusy(null);
    }
  };
  return (
    <View accessibilityRole="summary" accessibilityLabel={`${name} veut t’écrire`} style={[card, enter('drop')]}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Voir le profil de ${name}`} onPress={onProfile}
        style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 12 }, pressed && { opacity: 0.8 }]}>
        <Avatar id={userId} name={name} photo={photo} size={44} profile={false} />
        <View style={{ flex: 1 }}>
          <Text accessibilityRole="header" style={[cf.display, { color: C.t1, fontSize: 19, lineHeight: 23 }]}>{name} veut t’écrire</Text>
          <Text style={[cf.text, { color: C.t2, fontSize: 13, lineHeight: 18 }]}>Demande de message · {name} ne sait pas si tu l’as lue</Text>
        </View>
      </Pressable>
      <Text style={[cf.text, { color: C.t2, fontSize: 14, lineHeight: 20 }]}>
        Accepte pour lui répondre. Supprimer efface la demande sans prévenir {name}.
      </Text>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <Pressable accessibilityRole="button" accessibilityLabel="Accepter" accessibilityState={{ busy: busy === 'accept' }} onPress={act('accept', onAccept)}
          style={({ pressed }) => [btn, pinkButton, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
          {busy === 'accept' ? <ActivityIndicator size="small" color={C.onPink} /> : null}
          <Text style={[cf.bold, { color: C.onPink, fontSize: 16 }]}>Accepter</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Supprimer la demande" accessibilityState={{ busy: busy === 'delete' }} onPress={act('delete', onDelete)}
          style={({ pressed }) => [btn, { backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine }, pressTransition, pressed && { opacity: 0.7 }]}>
          <Text style={[cf.bold, { color: C.t1, fontSize: 16 }]}>Supprimer</Text>
        </Pressable>
      </View>
      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6 }}>
        {confirmBlock ? (
          <>
            <Small label="Confirmer le blocage" danger onPress={act('block', onBlock)} busy={busy === 'block'} />
            <Small label="Annuler" onPress={() => setConfirmBlock(false)} />
          </>
        ) : (
          <>
            <Small label={`Bloquer ${name}`} icon="block" danger onPress={() => setConfirmBlock(true)} />
            <Small label="Signaler" icon="flag" onPress={onReport} />
          </>
        )}
      </View>
      {error ? <Text accessibilityRole="alert" style={[cf.text, { color: C.danger, fontSize: 13 }]}>{error}</Text> : null}
    </View>
  );
}

function Small({ label, icon, danger, onPress, busy }: { label: string; icon?: 'block' | 'flag'; danger?: boolean; onPress: () => void; busy?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [{ minHeight: 44, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 22 }, pressed && { backgroundColor: C.glass }]}>
      {busy ? <ActivityIndicator size="small" color={C.danger} /> : icon ? <Icon name={icon} size={16} color={danger ? C.danger : C.t2} /> : null}
      <Text style={[cf.semibold, { color: danger ? C.danger : C.t2, fontSize: 14 }]}>{label}</Text>
    </Pressable>
  );
}

const card = [{ marginHorizontal: 12, marginTop: 12, padding: 16, gap: 12, borderRadius: 22, borderWidth: 1, borderColor: 'rgba(185,167,255,0.22)' },
  web({ backgroundColor: C.s1, backgroundImage: 'radial-gradient(120% 90% at 0% 0%, rgba(123,108,246,0.24), transparent 60%)',
    boxShadow: '0 18px 40px -22px rgba(0,0,0,0.8)' })];
const btn = { flex: 1, minHeight: 48, borderRadius: 24, flexDirection: 'row' as const, alignItems: 'center' as const, justifyContent: 'center' as const, gap: 8 };
