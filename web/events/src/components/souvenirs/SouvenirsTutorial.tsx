import { useCallback, useState } from 'react';

/**
 * Didacticiel des Souvenirs : EMPLACEMENT RÉSERVÉ (24.11). Un autre agent l'écrit APRÈS les écrans web.
 *
 * Où il s'ouvre : `SouvenirsCard` (components/souvenirs/SouvenirsCard.tsx) le monte quand la carte Souvenirs d'une fiche
 * s'affiche pour la PREMIÈRE fois sur cet appareil (`useSouvenirsTutorial().visible`), et aussi sur « ❔ Comment ça marche »
 * (`show()`), avec la vue qui convient (`staff` : organisation, `keep` : enregistrement autorisé ou non).
 * Ce qu'il doit faire : afficher ses cartes, puis appeler `onDone()` (qui retient « déjà vu » dans localStorage).
 *
 * TODO(didacticiel) : écrire le contenu (cartes, animations, textes de la maquette souvenirs-v2.html). Tant qu'il renvoie
 * null, rien ne s'affiche et « déjà vu » n'est PAS retenu : le futur didacticiel s'ouvrira bien à la 1re ouverture.
 */
/** TODO(didacticiel) : passer à true avec le contenu ; « ❔ Comment ça marche » s'affiche alors sur la carte. */
export const TUTORIAL_READY = false;

export function SouvenirsTutorial(_props: { visible: boolean; staff: boolean; keep: boolean; onDone: () => void }) {
  return null;
}

const SEEN_KEY = 'party-souvenirs-tutorial-seen';

/** « Déjà vu » par appareil (stockage indisponible : il ne s'ouvre qu'à la demande). */
export function useSouvenirsTutorial() {
  const [seen, setSeen] = useState(() => {
    try { return localStorage.getItem(SEEN_KEY) === '1'; } catch { return true; }
  });
  const [asked, setAsked] = useState(false);
  const done = useCallback(() => {
    try { localStorage.setItem(SEEN_KEY, '1'); } catch { /* sans stockage : vaut pour cette page */ }
    setSeen(true);
    setAsked(false);
  }, []);
  return { visible: !seen || asked, show: () => setAsked(true), done };
}
