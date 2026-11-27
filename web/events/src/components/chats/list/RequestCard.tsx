import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { chatFont, useNeon, web } from '../neon';
import { PersonFace } from './Faces';
import { listTime, previewText } from './format';
import { Icon } from './Icons';
import { usePersonText } from '@/components/PersonName';
import { ConfirmButton } from '@/components/ui';
import type { ChatItem } from '@/lib/chatList';
import { enter, pressTransition } from '@/lib/motion';

type Props = {
  chat: ChatItem; index: number; busy: boolean;
  onProfile: () => void; onAccept: () => void; onDecline: () => void; onBlock: () => void; onReport: () => void;
};

/**
 * Une demande de message (contrat §2, §8) : la personne (toucher → mini-profil), son unique message texte, puis
 * Accepter / Supprimer, et Bloquer · Signaler discrets. Ni « Vu » ni « écrit… » : elle ne sait pas que tu l'as lue.
 */
export function RequestCard({ chat, index, busy, onProfile, onAccept, onDecline, onBlock, onReport }: Props) {
  const c = useNeon();
  const personText = usePersonText();
  const name = chat.user_id ? personText(chat.user_id, chat.title) : chat.title;
  const [confirm, setConfirm] = useState(false);
  return (
    <View style={[st.card, { backgroundColor: c.glass, borderColor: c.glassLine }, enter('rise', index)]} accessibilityLabel={`Demande de ${name}`}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Voir le profil de ${name}`} onPress={onProfile}
        style={({ pressed }) => [st.who, pressed && { opacity: 0.7 }]}>
        <PersonFace id={chat.user_id ?? chat.id} name={chat.title} photo={chat.photo} path={chat.avatar_path} size={54} />
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text numberOfLines={1} style={[chatFont.display, { color: c.t1, fontSize: 19, lineHeight: 23 }]}>{name}</Text>
          <Text numberOfLines={1} style={[chatFont.text, { color: c.t2, fontSize: 14 }]}>
            veut t’écrire{chat.last ? ` · ${listTime(chat.last.at)}` : ''}
          </Text>
        </View>
        <Icon name="chevr" size={18} color={c.t3} />
      </Pressable>

      {chat.last ? (
        <View style={[st.bubble, { backgroundColor: c.theirs, borderColor: c.theirsLine }]}>
          <Text style={[chatFont.text, { color: c.t1, fontSize: 17, lineHeight: 23 }]}>{previewText(chat.last)}</Text>
        </View>
      ) : null}

      <View style={st.buttons}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Accepter la demande de ${name}`} disabled={busy} onPress={onAccept}
          style={({ pressed }) => [st.btn, { flex: 1 }, web({ backgroundImage: `linear-gradient(135deg, ${c.pinkA}, ${c.pink})`,
            boxShadow: '0 0 0 1px rgba(255,255,255,.25) inset, 0 12px 26px -12px rgba(255,79,154,.8)' }), busy && { opacity: 0.6 },
          pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
          <Text style={[chatFont.bold, { color: c.onPink, fontSize: 17 }]}>Accepter</Text>
        </Pressable>
        {/* Règle de l'admin : toute suppression demande une confirmation. */}
        <ConfirmButton label="Supprimer" accessibilityLabel={`Supprimer la demande de ${name}`} confirmLabel="Oui, supprimer la demande" style={{ flex: 1 }} onConfirm={onDecline} />
      </View>

      {confirm ? (
        <View style={[st.confirm, { borderColor: c.line }]}>
          <Text style={[chatFont.text, { color: c.t2, fontSize: 14, lineHeight: 19 }]}>
            {name} ne pourra plus t’écrire. Les modérateurs sont prévenus. Tu peux débloquer dans Réglages › Confidentialité.
          </Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Pressable accessibilityRole="button" accessibilityLabel="Annuler" onPress={() => setConfirm(false)} style={[st.small, { borderColor: c.line2 }]}>
              <Text style={[chatFont.semibold, { color: c.t1, fontSize: 15 }]}>Annuler</Text>
            </Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={`Confirmer : bloquer ${name}`} onPress={() => { setConfirm(false); onBlock(); }}
              style={[st.small, { borderColor: c.danger, flex: 1 }]}>
              <Text style={[chatFont.bold, { color: c.danger, fontSize: 15 }]}>Bloquer {name}</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <View style={st.quiet}>
          <Pressable accessibilityRole="button" accessibilityLabel={`Bloquer ${name}`} onPress={() => setConfirm(true)} style={st.link}>
            <Icon name="block" size={15} color={c.t3} />
            <Text style={[chatFont.semibold, { color: c.t2, fontSize: 14 }]}>Bloquer</Text>
          </Pressable>
          <Text style={{ color: c.t3 }} aria-hidden>·</Text>
          <Pressable accessibilityRole="button" accessibilityLabel={`Signaler la demande de ${name}`} onPress={onReport} style={st.link}>
            <Icon name="flag" size={15} color={c.t3} />
            <Text style={[chatFont.semibold, { color: c.t2, fontSize: 14 }]}>Signaler</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

const st = StyleSheet.create({
  card: { marginHorizontal: 16, marginTop: 12, padding: 14, paddingBottom: 4, borderRadius: 22, borderWidth: 1, gap: 12 },
  who: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  bubble: { alignSelf: 'flex-start', maxWidth: '92%', borderRadius: 22, borderBottomLeftRadius: 8, borderWidth: 1, paddingHorizontal: 13, paddingTop: 9, paddingBottom: 9 },
  buttons: { flexDirection: 'row', gap: 10 },
  btn: { height: 50, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  quiet: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: -4 },
  link: { flexDirection: 'row', alignItems: 'center', gap: 6, height: 44, paddingHorizontal: 10 },
  confirm: { gap: 10, paddingTop: 10, borderTopWidth: 1 },
  small: { height: 44, paddingHorizontal: 14, borderRadius: 14, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
});
