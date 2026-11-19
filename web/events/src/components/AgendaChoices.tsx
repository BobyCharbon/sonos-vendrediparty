import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { agendaApps, subscribeLink, type AgendaApp } from '@/lib/calendar';
import { copyText } from '@/lib/invites';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

import { T } from './ui';

export type AgendaChoice = AgendaApp | 'file';

const LABELS: Record<AgendaChoice, { label: string; hint: string }> = {
  apple: { label: 'Calendrier Apple', hint: 'iPhone, iPad, Mac' },
  google: { label: 'Google Agenda', hint: 'Compte Google' },
  outlook: { label: 'Outlook', hint: 'Outlook.com, Hotmail' },
  copy: { label: 'Samsung ou autre agenda', hint: 'Copier le lien de ton agenda' },
  file: { label: 'Juste cet événement', hint: 'Un fichier à ouvrir, sans mise à jour' },
};

/**
 * Choix de l'agenda (avis du 19.11) : sous Android, tout partait dans Google Agenda. Chacun choisit le sien ; « Samsung ou
 * autre » copie le lien du calendrier « Vendredi Party » (à coller dans l'agenda, ou dans l'app ICSx⁵ pour Samsung).
 */
export function AgendaChoices({ token, onPick, file = false }: { token: string | null; onPick: (choice: AgendaChoice) => void; file?: boolean }) {
  const [copied, setCopied] = useState<boolean | null>(null);
  const feed = token && typeof window !== 'undefined' ? subscribeLink(token, window.location.origin, 'copy') : null;
  const choices: AgendaChoice[] = [...(token ? agendaApps() : (['google'] as AgendaApp[])), ...(file ? (['file'] as const) : [])];

  const pick = (choice: AgendaChoice) => {
    if (choice === 'copy' && feed) void copyText(feed).then(setCopied);  // dans le toucher, sinon le navigateur refuse
    onPick(choice);
  };

  return (
    <View style={[{ gap: 8 }, enter('drop')]} accessibilityLabel="Choisis ton agenda">
      <T size={13} muted style={{ textAlign: 'center' }}>Choisis ton agenda :</T>
      {choices.map((c) => (
        <Pressable key={c} accessibilityRole="button" accessibilityLabel={LABELS[c].label} onPress={() => pick(c)}
          style={({ pressed }) => [st.choice, pressTransition, pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] }]}>
          <T size={14} style={{ ...font.bold }}>{LABELS[c].label}</T>
          <T size={12} muted>{LABELS[c].hint}</T>
        </Pressable>
      ))}
      {copied !== null && feed ? (
        <View style={st.copied}>
          <T size={13} weight="semibold" color={copied ? colors.mint : colors.text}>{copied ? '✓ Lien copié' : 'Copie ce lien :'}</T>
          <T size={12} color={colors.textSoft} style={{ userSelect: 'all', wordBreak: 'break-all' } as object}>{feed}</T>
          <T size={12} muted>
            Dans ton agenda : « Ajouter un calendrier » › « Depuis une adresse (URL) ». Samsung Agenda ne le permet pas :
            l’app gratuite ICSx⁵ l’y ajoute. Ce lien est à toi seul : ne le partage pas.
          </T>
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  choice: { minHeight: 52, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 8, justifyContent: 'center', gap: 2, backgroundColor: colors.fill },
  copied: { gap: 6, padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line },
});
