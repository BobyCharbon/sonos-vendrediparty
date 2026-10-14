// Notifications push : abonnement de cet appareil (page invités : portée « / », admin : « /admin »).
const Push = {
  // iPhone : uniquement depuis l'app ajoutée à l'écran d'accueil (iOS 16.4+).
  supported: () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window,

  async current(scope) {
    if (!Push.supported()) return null;
    const reg = await navigator.serviceWorker.getRegistration(scope);
    // getRegistration renvoie aussi une portée plus large (« / » pour l'admin) : on veut la sienne.
    return reg && new URL(reg.scope).pathname === scope ? reg.pushManager.getSubscription() : null;
  },

  async subscribe(scope, url, extra = {}) {
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
