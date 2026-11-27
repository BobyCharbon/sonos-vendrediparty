import { Linking, Platform, Text } from 'react-native';

import { T } from './ui';
import { SUPPORT_EMAIL } from '@/lib/contact';
import { colors } from '@/lib/theme';

/**
 * Pages d'invitation (carte d'un événement, groupe, « X t'invite sur Party ») : on peut les lire avant de pouvoir
 * signaler dans l'app (pas de compte, demande en attente d'accord). Apple 1.2 : un « Signaler » quand même, par e-mail
 * (contrôle du 27.11). `subject` : ce qui permet à la modération de retrouver l'invitation.
 */
export function InviteReportLine({ subject }: { subject: string }) {
  const href = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`Signalement : ${subject}`)}`;
  // Web : un vrai <a>, fenêtre principale (_top) : dans le cadre du module, mailto: ne s'ouvrirait pas (LinkedText).
  const webProps = Platform.OS === 'web' ? ({ href, hrefAttrs: { target: '_top', rel: 'noopener noreferrer' } } as object) : {};
  return (
    <T muted size={12} style={{ textAlign: 'center' }}>
      <Text accessibilityRole="link" accessibilityLabel="Signaler cette invitation par e-mail" testID="invite-report" {...webProps}
        onPress={Platform.OS === 'web' ? undefined : () => void Linking.openURL(href)}
        style={{ color: colors.textSoft, textDecorationLine: 'underline' }}>
        🚩 Signaler cette invitation
      </Text>
      {` · Traité sous 24 h · ${SUPPORT_EMAIL}`}
    </T>
  );
}
