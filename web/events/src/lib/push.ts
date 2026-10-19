import { check, must, supabase } from './supabase';

const scope = '/events/';
export type WebPushState = {
  supported: boolean;
  needsInstall: boolean;
  permission: NotificationPermission | 'unavailable';
  subscribed: boolean;
};

function capabilities(): Omit<WebPushState, 'subscribed'> {
  const available = typeof window !== 'undefined';
  const ios = available && (/iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1));
  const standalone = available && (window.matchMedia('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true);
  return {
    supported: available && window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
    needsInstall: !!ios && !standalone,
    permission: available && 'Notification' in window ? Notification.permission : 'unavailable',
  };
}

async function current() {
  if (!capabilities().supported) return null;
  const registration = await navigator.serviceWorker.getRegistration(scope);
  return registration && new URL(registration.scope).pathname === scope
    ? registration.pushManager.getSubscription() : null;
}

async function register(subscription: PushSubscription) {
  check(await supabase.rpc('register_web_push', {
    device_subscription: subscription.toJSON(), device_origin: location.origin,
  }));
}

export async function webPushState(): Promise<WebPushState> {
  const base = capabilities();
  const subscription = await current();
  const subscribed = subscription && base.permission === 'granted'
    ? !!must(await supabase.rpc('web_push_device_status', { device_endpoint: subscription.endpoint })) : false;
  return { ...base, subscribed };
}

export async function enableWebPush(): Promise<WebPushState> {
  const base = capabilities();
  if (base.needsInstall) throw new Error('Ajoute Party à l’écran d’accueil depuis Safari, puis ouvre son icône pour activer les notifications.');
  if (!base.supported) throw new Error('Ce navigateur ne propose pas les notifications web. Ouvre Party dans un navigateur compatible en HTTPS.');
  // Garder la demande dans le geste de l’utilisateur, avant tout appel réseau.
  if (await Notification.requestPermission() !== 'granted') {
    throw new Error('Notifications non autorisées. Tu peux les autoriser dans les réglages du navigateur ; les annonces restent dans Activité.');
  }
  const publicKey = must(await supabase.rpc('get_web_push_public_key')) as string | null;
  if (!publicKey) throw new Error('Le service de notifications démarre. Réessaie dans une minute.');
  const registration = await navigator.serviceWorker.register('/sw.js', { scope });
  if (!registration.active) {
    const worker = registration.installing ?? registration.waiting;
    if (!worker) throw new Error('Impossible de préparer les notifications. Recharge la page puis réessaie.');
    await new Promise<void>((resolve, reject) => {
      const changed = () => {
        if (worker.state === 'activated') { clearTimeout(timer); worker.removeEventListener('statechange', changed); resolve(); }
        else if (worker.state === 'redundant') { clearTimeout(timer); worker.removeEventListener('statechange', changed); reject(new Error('Activation interrompue. Recharge la page puis réessaie.')); }
      };
      const timer = setTimeout(() => { worker.removeEventListener('statechange', changed); reject(new Error('Activation trop longue. Recharge la page puis réessaie.')); }, 15000);
      worker.addEventListener('statechange', changed);
      changed();
    });
  }
  const raw = atob(publicKey.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - publicKey.length % 4) % 4));
  const subscription = await registration.pushManager.getSubscription()
    ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: Uint8Array.from(raw, (c) => c.charCodeAt(0)) });
  await register(subscription);
  return webPushState();
}

/** Réassocier seulement un appareil déjà autorisé, sans demande système. */
export async function syncWebPush() {
  const subscription = capabilities().permission === 'granted' ? await current() : null;
  if (subscription) await register(subscription);
}

export async function testWebPush() {
  const subscription = await current();
  if (!subscription) throw new Error('Active d’abord les notifications sur cet appareil.');
  check(await supabase.rpc('test_web_push', { device_endpoint: subscription.endpoint }));
}

export async function unregisterPushToken() {
  const subscription = await current();
  if (!subscription) return;
  try {
    check(await supabase.rpc('unregister_web_push', { device_endpoint: subscription.endpoint }));
  } finally {
    // Ni l’abonnement musique ni celui de l’admin musique ne sont touchés.
    await subscription.unsubscribe();
  }
}
