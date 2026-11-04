import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking } from 'react-native';

import { Button, Screen, Section, T, Title } from '@/components/ui';
import { moderationInfo, type PublicInfo } from '@/lib/moderation';
import { TERMS_SECTIONS, TERMS_UPDATED } from '@/lib/terms';

/** Conditions d'utilisation de Party (Apple 1.2, Google UGC) : lisibles par tous, même sans compte ; acceptées par
 * chaque compte avant son premier contenu (Réglages › Confidentialité). Le texte vit dans lib/terms.ts. */
export default function Terms() {
  const [info, setInfo] = useState<PublicInfo | null>(null);
  useEffect(() => { void moderationInfo().then(setInfo); }, []);
  const contact = info?.contact_email ?? null;
  return (
    <Screen edges={[]}>
      <Title>Conditions d’utilisation</Title>
      <T muted>Party · Version du {TERMS_UPDATED}</T>
      {TERMS_SECTIONS.map((section) => (
        <Section key={section.title} title={section.title}>
          {section.paragraphs.map((p) => <T key={p}>{p}</T>)}
        </Section>
      ))}
      <Section title="Contact">
        {contact ? (
          <>
            <T>Une question, un contenu à signaler en dehors de l’app, une demande sur tes données : écris à {contact}.</T>
            <Button small variant="secondary" label={`Écrire à ${contact}`} onPress={() => void Linking.openURL(`mailto:${contact}`)} />
          </>
        ) : (
          <T>Une question ou une demande sur tes données : utilise « Signaler » dans l’app ou contacte l’administrateur du groupe.</T>
        )}
      </Section>
      <Button label="Revenir à l’application" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
    </Screen>
  );
}
