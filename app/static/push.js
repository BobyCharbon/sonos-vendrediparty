// Notifications push : abonnement de cet appareil (page invités : portée « / », admin : « /admin »).
// App iOS native (ios/) : une WKWebView n'a pas Web Push. L'app inscrit l'appareil auprès d'Apple (APNs,
// window.PartyNative.push) et l'abonnement devient { endpoint: "apns:<jeton>", apns: {…} } (app/apns.py).
// Les pages utilisent la même interface dans les deux cas. Tests : tests/e2e/test_native_push.py.
const NativePush = (() => {
  const bridge = window.PartyNative && window.PartyNative.push;
  if (!bridge) return null;
  const key = (scope) => `vp_native_push:${scope}`;
  let permission = "default";
  const refresh = () => bridge.status().then((r) => { permission = r.status; }, () => {});
  refresh();
  // Même forme qu'un abonnement Web Push : .endpoint et .toJSON().
  const subscription = (data) => ({ endpoint: data.endpoint, toJSON: () => data });
  const saved = (scope) => { try { return JSON.parse(localStorage.getItem(key(scope))); } catch { return null; } };

  return {
    permission: () => permission,

    async current(scope) {
      const data = saved(scope);
      if (!data) return null;
      await refresh();
      return permission === "granted" ? subscription(data) : null;
    },

    async subscribe(scope, url, extra) {
      let device;
      try {
        device = await bridge.register();
      } catch (e) {
        await refresh();
        throw new Error(e.message || "Notifications refusées : autorise-les pour Party ! dans les réglages du téléphone");
      }
      permission = "granted";
      const data = { endpoint: `apns:${device.token}`,
                     apns: { token: device.token, environment: device.environment, topic: device.bundleId } };
      await Push.send(url, { ...extra, subscription: data });
      try { localStorage.setItem(key(scope), JSON.stringify(data)); } catch { /* navigation privée : sans souvenir */ }
      return subscription(data);
    },

    async unsubscribe(scope) {
      const data = saved(scope);
      if (!data) return;
      await Push.send("/api/push/unsubscribe", { endpoint: data.endpoint }).catch(() => {});
      try { localStorage.removeItem(key(scope)); } catch { /* rien à oublier */ }
    },
  };
})();

const Push = {
  // iPhone : depuis l'app native, ou depuis l'app ajoutée à l'écran d'accueil (iOS 16.4+).
  supported: () => !!NativePush || ("serviceWorker" in navigator && "PushManager" in window && "Notification" in window),

  /** « granted », « denied » ou « default », comme Notification.permission. */
  permission: () => (NativePush ? NativePush.permission() : ("Notification" in window ? Notification.permission : "default")),

  async current(scope) {
    if (NativePush) return NativePush.current(scope);
    if (!Push.supported()) return null;
    const reg = await navigator.serviceWorker.getRegistration(scope);
    // getRegistration renvoie aussi une portée plus large (« / » pour l'admin) : on veut la sienne.
    return reg && new URL(reg.scope).pathname === scope ? reg.pushManager.getSubscription() : null;
  },

  async subscribe(scope, url, extra = {}) {
    if (NativePush) return NativePush.subscribe(scope, url, extra);
    if (await Notification.requestPermission() !== "granted") {
      throw new Error("Notifications refusées : autorise-les pour ce site dans les réglages du téléphone");
    }
    const reg = await navigator.serviceWorker.register("/sw.js", { scope });
    if (!reg.active) {
      // Premier enregistrement : on attend que le service worker soit actif.
      await new Promise((ok) => {
        const sw = reg.installing || reg.waiting;
        sw.addEventListener("statechange", () => sw.state === "activated" && ok());
      });
    }
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      const { key } = await (await fetch("/api/push/key")).json();
      const raw = atob(key.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - key.length % 4) % 4));
      sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: Uint8Array.from(raw, (c) => c.charCodeAt(0)) });
    }
    await Push.send(url, { ...extra, subscription: sub.toJSON() });
    return sub;
  },

  async unsubscribe(scope) {
    if (NativePush) return NativePush.unsubscribe(scope);
    const sub = await Push.current(scope);
    if (!sub) return;
    await Push.send("/api/push/unsubscribe", { endpoint: sub.endpoint }).catch(() => {});
    await sub.unsubscribe();
  },

  async send(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Erreur");
  },
};
