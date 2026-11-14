// Service worker : uniquement pour les notifications push (aucune mise en cache).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (ev) => ev.waitUntil(self.clients.claim()));

self.addEventListener("push", (ev) => {
  let d = {};
  try { d = ev.data ? ev.data.json() : {}; } catch {}
  ev.waitUntil(self.registration.showNotification(d.title || "VendrediParty", {
    body: d.body || "",
    icon: "/static/icon-192.png?v=3",
    tag: d.tag,
    renotify: d.silent !== true && !!d.tag && !String(d.tag).startsWith("party-event-"),
    data: { url: d.url || "/" },
    // Pause des notifications (lune, Discussions) : livrée sans son ni vibration.
    silent: d.silent === true,
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
      try {
        // Un événement ouvre sa fiche dans l’onglet, même si Musique était affiché. Toujours : open.url garde
        // l’adresse d’arrivée (history.replaceState ne la change pas), la comparer laissait la page sur place.
        // Page que ce service worker ne contrôle pas (abonnement Événements, portée /events/) : navigate() est
        // refusé ; la page ouvre alors l’adresse elle-même (push.js), au lieu d’un 2e Party.
        if (url.search || url.hash) {
          await open.navigate(url.href).catch(() => open.postMessage({ type: "party-open", url: url.href }));
        }
        return await open.focus();
      } catch { /* L’onglet peut avoir été fermé pendant le clic : en ouvrir un autre. */ }
    }
    await self.clients.openWindow(url.href);
  })());
});
