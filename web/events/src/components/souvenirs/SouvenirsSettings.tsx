import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Rows, T, ToggleRow } from '@/components/ui';
import { colors, font, radius } from '@/lib/theme';

import { SouvenirsTutorial, useSouvenirsTutorial } from './SouvenirsTutorial';

const ORANGE = '#FF9F43';

/**
 * Réglage de l'organisateur (maquette v2, écran 1), dans le formulaire de l'événement à côté du covoiturage :
 * « 📸 Souvenirs » (éteint par défaut, jamais allumé par l'IA) et « Autoriser l'enregistrement » (ALLUMÉ par défaut ;
 * coupé : l'avertissement orange, avec la phrase honnête sur les captures). Figés dès la 1re photo (la base refuse).
 */
export function SouvenirsSettings({ enabled, keep, locked, onChange }: {
  enabled: boolean; keep: boolean; locked: boolean; onChange: (v: { souvenirs_enabled?: boolean; souvenirs_keep?: boolean }) => void;
}) {
  const tutorial = useSouvenirsTutorial(false);
  return (
    <View style={{ gap: 10 }} testID="souvenirs-settings">
      <Rows>
        <ToggleRow label="📸 Souvenirs" disabled={locked} value={enabled} onChange={(v) => onChange({ souvenirs_enabled: v })}
          hint="Un appareil jetable de 3 poses pour chaque participant, dévoilé en story 24 h après la fin." />
        {enabled ? (
          <ToggleRow label="Autoriser l’enregistrement" disabled={locked} value={keep} onChange={(v) => onChange({ souvenirs_keep: v })}
            hint="Pendant la story, chacun peut garder les photos qu’il préfère dans ses souvenirs." />
        ) : null}
      </Rows>
      {enabled && keep ? (
        <View style={st.ok}>
          <Text>✅</Text>
          <T muted size={13} style={{ flex: 1 }}>
            Les 3 photos de chacun seront montrées à tous les participants pendant 24 h. Chacun pourra garder ses préférées dans ses souvenirs (13 mois).
          </T>
        </View>
      ) : null}
      {enabled && !keep ? (
        <View style={st.warn} accessibilityRole="alert">
          <Text style={{ fontSize: 20, lineHeight: 22 }}>⚠️</Text>
          <View style={{ flex: 1 }}>
            <Text style={st.warnTitle}>Enregistrement désactivé</Text>
            <Text style={st.warnText}>
              Les photos ne resteront dans les souvenirs de personne : elles disparaissent après la story. Captures bloquées dans
              l’app iPhone seulement ; ailleurs, rien ne peut l’empêcher.
            </Text>
          </View>
        </View>
      ) : null}
      {enabled ? (
        <T muted size={12} style={{ lineHeight: 18 }}>
          Présents, Peut-être et organisation · l’organisation peut relire les photos avant le dévoilement et en retirer · du début à la
          fin + 2 h · photo jamais revue après la prise · dévoilement 24 h après la fin (tu peux l’avancer) · story visible 24 h ·
          position et données de l’appareil retirées des photos.
        </T>
      ) : null}
      {enabled ? (
        <Pressable accessibilityRole="button" testID="souvenirs-settings-help" onPress={tutorial.show} style={{ alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center' }}>
          <T size={14} weight="semibold" color={colors.accentSoft}>❔ Comment ça marche</T>
        </Pressable>
      ) : null}
      <SouvenirsTutorial visible={tutorial.visible} staff keep={keep} onSkip={tutorial.skip} onNever={tutorial.never} />
      {locked ? (
        <T size={13} color={colors.coralSoft}>
          🔒 Réglages figés depuis la première photo : les participants ont pris leurs photos en sachant ce qu’elles deviendraient.
        </T>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  ok: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  warn: { flexDirection: 'row', gap: 10, padding: 12, paddingHorizontal: 14, borderRadius: radius.md, borderWidth: 1.5, borderColor: ORANGE, backgroundColor: 'rgba(255,159,67,0.13)' },
  warnTitle: { color: ORANGE, fontSize: 14, marginBottom: 2, ...font.bold },
  warnText: { color: colors.text, fontSize: 14, lineHeight: 20, ...font.body },
});
