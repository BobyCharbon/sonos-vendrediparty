// Service worker : uniquement pour les notifications push (aucune mise en cache).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (ev) => ev.waitUntil(self.clients.claim()));

self.addEventListener("push", (ev) => {
  let d = {};
  try { d = ev.data ? ev.data.json() : {}; } catch {}
  ev.waitUntil(self.registration.showNotification(d.title || "VendrediParty", {
    body: d.body || "",
    icon: "/static/icon-192.png",
    tag: d.tag,
    renotify: !!d.tag && !String(d.tag).startsWith("party-event-"),
    data: { url: d.url || "/" },
  }));
});

self.addEventListener("notificationclick", (ev) => {
  ev.notification.close();
  let url;
  try { url = new URL(ev.notification.data?.url || "/", self.location.origin); } catch { url = new URL("/", self.location.origin); }
  if (url.origin !== self.location.origin) url = new URL("/", self.location.origin);
  ev.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    // Une page déjà ouverte (invités ou admin) est remise au premier plan plutôt que d'en ouvrir une autre.
    const open = wins.find((w) => new URL(w.url).origin === url.origin && new URL(w.url).pathname === url.pathname);
    if (open) {
      // Un événement ouvre sa fiche dans l’onglet, même si Musique était affiché.
      if (url.search && open.url !== url.href) await open.navigate(url.href);
      return open.focus();
    }
    await self.clients.openWindow(url.href);
  })());
});
