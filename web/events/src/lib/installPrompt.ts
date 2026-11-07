/** « Installer Party » selon l'appareil (campagne 2, 07.11 : sur Android le bouton ouvrait l'App Store d'Apple).
 * iPhone, iPad, ordinateur : l'App Store (ou TestFlight sur le site de test). Android : la page web s'installe sur
 * l'écran d'accueil quand Chrome le propose (beforeinstallprompt), sinon pas de bouton. */

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice?: Promise<{ outcome: string }> };

let deferred: InstallEvent | null = null;

if (typeof window !== 'undefined') {
  // Chrome l'envoie tôt, avant que l'écran de confirmation ne s'affiche : on le garde pour le geste de la personne.
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferred = e as InstallEvent;
  });
}

export function isAndroid(): boolean {
  return typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent);
}

/** Android : l'installation de la page est-elle possible maintenant ? */
export function canInstallWebApp(): boolean {
  return deferred !== null;
}

/** Ouvre la fenêtre d'installation de Chrome ; false si elle n'est pas disponible ou refusée. */
export async function installWebApp(): Promise<boolean> {
  const event = deferred;
  if (!event) return false;
  deferred = null;  // Chrome ne la propose qu'une fois
  await event.prompt();
  const choice = await event.userChoice?.catch(() => null);
  return choice?.outcome !== 'dismissed';
}
