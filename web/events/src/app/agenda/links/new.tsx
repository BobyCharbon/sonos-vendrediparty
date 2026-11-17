import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useState } from 'react';

import { goBack, TopBar } from '@/components/agenda/Bits';
import { LinkEditor, LinkIntro } from '@/components/agenda/LinkEditor';
import { Screen } from '@/components/ui';
import { MODELS, type Model } from '@/lib/agenda';

/** Nouveau lien de dispo : d'abord ce que le lien donne (maquette 6B, à chaque nouveau lien), puis son réglage (6C, 6D). */
export default function NewLinkScreen() {
  const p = useLocalSearchParams<{ model?: string }>();
  const model = MODELS.some((m) => m.key === p.model) ? (p.model as Model) : 'week';
  const [step, setStep] = useState<'intro' | 'edit'>('intro');
  return (
    <Screen>
      <TopBar back="Mes liens" fallback="/agenda/links" title={step === 'edit' ? 'Nouveau lien' : undefined} />
      {step === 'intro' ? <LinkIntro onGo={() => setStep('edit')} onCancel={() => goBack('/agenda/links')} /> : (
        <LinkEditor link={null} model={model} onSaved={(l) => router.replace(`/agenda/links/${l.id}?created=1` as Href)} />
      )}
    </Screen>
  );
}
