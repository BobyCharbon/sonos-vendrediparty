import { router, type Href } from 'expo-router';
import { View } from 'react-native';

import { ast, goBack, TopBar } from '@/components/agenda/Bits';
import { CheckLine, loadSetup, setupHref, SetupBar, sharedLabel } from '@/components/agenda/Tutorial';
import { Button, ErrorText, Screen, T } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { groupName } from '@/lib/groups';
import { enter } from '@/lib/motion';
import { colors } from '@/lib/theme';

/** Assistant, étape 3 « C'est prêt » : ce qui est fait, ce qui reste (on peut y revenir), puis « Voir qui est libre ». */
export default function SetupDoneScreen() {
  const { data, error } = useQuery(loadSetup, []);
  const first = data?.shared[0];
  return (
    <Screen>
      <TopBar back="Agenda" fallback="/agenda" />
      <SetupBar step={3} hint="Tu pourras tout changer quand tu veux dans Calendriers." />
      <ErrorText error={error} />
      {data ? (
        <View style={[ast.card, enter('pop')]} testID="setup-done">
          <T size={40}>🎉</T>
          <T size={20} weight="bold">{data.linked && data.shared.length ? 'Tout est en place !' : 'C’est parti !'}</T>
          <CheckLine done label="Tes soirées Party sont dans ton agenda" />
          <CheckLine done={data.linked} label={data.linked ? 'Agendas reliés' : 'Agendas pas encore reliés'} />
          <CheckLine done={!!data.shared.length} label={data.shared.length
            ? `${sharedLabel(data.shared.length)} (${data.shared.map((g) => groupName(g)).join(', ')})`
            : 'Rien de partagé pour l’instant'} />
          {!data.linked || !data.shared.length ? (
            <T size={14} color={colors.textSoft}>Pas de souci : tu peux le faire plus tard depuis l’accueil de l’agenda.</T>
          ) : null}
        </View>
      ) : null}
      <View style={ast.bottom}>
        <Button label="👥 Voir qui est libre" onPress={() => router.replace((first ? `/agenda/free?group=${first.id}` : '/agenda/free') as Href)} />
        {data && !data.linked ? <Button label="Relier mes agendas" variant="secondary" onPress={() => router.replace(setupHref(1))} /> : null}
        <Button label="Retour à l’agenda" variant="ghost" onPress={() => goBack('/agenda')} />
      </View>
    </Screen>
  );
}
