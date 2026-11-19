import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { AgendaChoices } from '@/components/AgendaChoices';
import { Screen, Section, T } from '@/components/ui';
import { myAgendaLink, openSubscription } from '@/lib/calendar';
import { colors } from '@/lib/theme';

/**
 * Réglages › Agenda Vendredi Party (avis du 19.11) : « Dans ton agenda » s'affiche dès qu'un agenda a lu le lien, même
 * si le téléphone ne l'a pas gardé. Ici, chacun le rajoute à tout moment dans l'agenda de son choix, sans passer par un événement.
 */
export default function CalendarSettings() {
  const [link, setLink] = useState<{ token: string; subscribed: boolean } | null | undefined>(undefined);
  const [opened, setOpened] = useState(false);
  useEffect(() => { void myAgendaLink().then(setLink); }, []);

  return (
    <Screen edges={[]}>
      <Section title="Agenda Vendredi Party">
        <T>Les événements où tu réponds Présent ou Peut-être (et les dates que tu votes) arrivent tout seuls dans ton agenda, et suivent chaque changement de date, d’heure ou de lieu.</T>
        {link === undefined ? <T muted>Chargement…</T> : link === null ? (
          <T color={colors.coralSoft}>Ton agenda n’a pas pu être préparé. Vérifie ta connexion et réessaie.</T>
        ) : (
          <View style={{ gap: 12 }}>
            <T size={14} weight="semibold" color={link.subscribed ? colors.mint : colors.textSoft}>
              {link.subscribed ? '✓ Un agenda a lu ton calendrier ces derniers jours. Pas sur ce téléphone ? Ajoute-le ci-dessous.' : 'Pas encore dans un agenda.'}
            </T>
            <AgendaChoices token={link.token} onPick={(c) => { if (c !== 'file') openSubscription(link.token, c); setOpened(c !== 'copy'); }} />
            {opened ? <T size={13} muted>Confirme l’abonnement « Vendredi Party » dans l’agenda qui s’ouvre.</T> : null}
          </View>
        )}
      </Section>
    </Screen>
  );
}
