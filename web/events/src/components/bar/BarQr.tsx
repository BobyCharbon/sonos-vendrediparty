import { Image, StyleSheet, View } from 'react-native';

import { colors, font, radius } from '@/lib/theme';
import { prettyCode, qrDataUri, ticketLink } from '@/lib/tickets';

import { T } from '../ui';

/**
 * Mon QR pour toute la soirée : le MÊME que le billet (jeton event_tickets, même lien que TicketCard), lu à l'entrée et
 * au bar. Sans caméra, le barman tape le code à 6 signes.
 */
export function BarQr({ eventId, qr }: { eventId: string; qr: { token: string; code: string } }) {
  const link = ticketLink(location.origin, eventId, qr.token);
  return (
    <View style={st.card}>
      <View style={st.qrBox}>
        <Image source={{ uri: qrDataUri(link) }} style={st.qr} accessibilityLabel="Mon QR pour le bar et l’entrée" />
      </View>
      <T size={13} color={colors.textSoft} style={{ textAlign: 'center' }}>Mon QR pour toute la soirée : entrée et bar</T>
      <View accessible accessibilityLabel={`Code ${qr.code.split('').join(' ')}`}>
        <T style={st.code}>{prettyCode(qr.code)}</T>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  card: { alignItems: 'center', gap: 8, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  qrBox: { width: '100%', maxWidth: 240, aspectRatio: 1, backgroundColor: '#fff', borderRadius: radius.md, padding: 8 },
  qr: { width: '100%', height: '100%' },
  code: { ...font.display, fontSize: 26, lineHeight: 30, letterSpacing: 4, textAlign: 'center', color: colors.text, fontVariant: ['tabular-nums'] },
});
