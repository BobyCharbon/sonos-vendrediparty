import { useEffect } from 'react';
import { Modal, Pressable, Text, View } from 'react-native';

import { C, cf, Icon, web, type IconName } from './kit';
import { SheetBackdrop } from '../../SheetGesture';
import { REACTIONS } from '@/lib/chats';
import { enter, pressTransition } from '@/lib/motion';

export type MenuAction = { key: string; label: string; icon: IconName; danger?: boolean; run: () => void };

type Props = {
  open: boolean;
  /** Aperçu du message (auteur et début du texte), en tête du menu. */
  preview: { author: string; text: string; mine: boolean } | null;
  /** Réactions (un toucher ajoute ou retire la mienne) ; absentes quand on ne peut pas écrire. */
  reactions: { emoji: string; mine: boolean }[] | null;
  onReact: (emoji: string) => void;
  actions: MenuAction[];
  onClose: () => void;
};

/** Menu d'un message (appui long, clic droit ou Entrée sur la bulle ; plus de « … » à côté de chaque bulle) : la barre
 * des 6 réactions puis les actions (Répondre, Répondre en privé, Copier, Modifier, Épingler, Supprimer, Signaler). */
export function MessageMenu({ open, preview, reactions, onReact, actions, onClose }: Props) {
  const run = (f: () => void) => () => { onClose(); f(); };
  // Échap ferme le menu (clavier), même quand une autre fenêtre du module garde la main sur celle de react-native-web.
  useEffect(() => {
    if (!open || typeof document === 'undefined') return undefined;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
      <View style={[{ flex: 1, justifyContent: 'flex-end', alignItems: 'center', padding: 12, paddingBottom: 24 },
        web({ backgroundColor: 'rgba(8,5,18,0.72)', backdropFilter: 'blur(6px)' })]}>
        <SheetBackdrop onPress={onClose} />
        <View accessibilityViewIsModal style={[{ width: '100%', maxWidth: 380, gap: 10 }, enter('pop')]}>
          {preview ? (
            <View style={[{ alignSelf: preview.mine ? 'flex-end' : 'flex-start', maxWidth: '88%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 20 },
              preview.mine ? web({ backgroundImage: `linear-gradient(160deg, ${C.mineA}, ${C.mineB})` }) : { backgroundColor: C.theirs, borderWidth: 1, borderColor: C.theirsLine }]}>
              {!preview.mine ? <Text style={[cf.bold, { color: C.lav, fontSize: 13 }]}>{preview.author}</Text> : null}
              <Text numberOfLines={4} style={[cf.text, { color: preview.mine ? '#fff' : C.t1, fontSize: 16, lineHeight: 21 }]}>{preview.text}</Text>
            </View>
          ) : null}
          {reactions ? (
            <View accessibilityRole="toolbar" accessibilityLabel="Réactions" style={[{ flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 8, paddingVertical: 6,
              borderRadius: 30, backgroundColor: C.sheet, borderWidth: 1, borderColor: C.line2 }, web({ boxShadow: '0 18px 40px -18px rgba(0,0,0,0.7)' })]}>
              {REACTIONS.map((emoji) => {
                const mine = reactions.some((r) => r.emoji === emoji && r.mine);
                return (
                  <Pressable key={emoji} accessibilityRole="button" accessibilityLabel={mine ? `Retirer ma réaction ${emoji}` : `Réagir ${emoji}`}
                    accessibilityState={{ selected: mine }} onPress={run(() => onReact(emoji))}
                    style={({ pressed }) => [{ width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
                      mine && { backgroundColor: 'rgba(185,167,255,0.22)' }, pressTransition, pressed && { transform: [{ scale: 1.25 }] }]}>
                    <Text style={{ fontSize: 26 }}>{emoji}</Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
          <View accessibilityRole="menu" style={[{ borderRadius: 20, overflow: 'hidden', backgroundColor: C.sheet, borderWidth: 1, borderColor: C.line2 },
            web({ boxShadow: '0 18px 40px -18px rgba(0,0,0,0.7)' })]}>
            {actions.map((a, i) => (
              <Pressable key={a.key} accessibilityRole="button" accessibilityLabel={a.label} onPress={run(a.run)}
                style={({ pressed, hovered }: { pressed: boolean; hovered?: boolean }) => [{ minHeight: 50, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 18 },
                  i > 0 && { borderTopWidth: 1, borderTopColor: C.line }, (pressed || hovered) && { backgroundColor: C.glass }]}>
                <Text style={[cf.semibold, { flex: 1, color: a.danger ? C.danger : C.t1, fontSize: 16 }]}>{a.label}</Text>
                <Icon name={a.icon} size={20} color={a.danger ? C.danger : C.lav} />
              </Pressable>
            ))}
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel="Fermer le menu" onPress={onClose}
            style={({ pressed }) => [{ minHeight: 50, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: C.s1,
              borderWidth: 1, borderColor: C.line2 }, pressed && { opacity: 0.7 }]}>
            <Text style={[cf.bold, { color: C.lav, fontSize: 16 }]}>Annuler</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
