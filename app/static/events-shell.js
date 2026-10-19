// Pont de navigation commun aux pages invités et admin. Aucune donnée de compte ici.
window.PartyEvents = {
  target(params, admin = false) {
    const id = params.get('event') || '';
    if (/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(id)) return '/events/event/' + id;
    if (params.get('activity') === '1') return '/events/activity';
    return admin ? '/events/admin' : '/events/';
  },
  open(target) {
    const frame = document.getElementById('eventsFrame');
    const loading = document.getElementById('eventsLoading');
    if (!frame) return;
    if (!frame.hasAttribute('src') || target) {
      loading?.classList.remove('hidden');
      frame.addEventListener('load', () => loading?.classList.add('hidden'), { once: true });
      frame.src = target || '/events/';
    }
  },
  /** Membres déjà connectés : charge le module en arrière-plan pour connaître les réponses attendues. */
  preload() {
    let session = false;
    try { session = Object.keys(localStorage).some((k) => /^sb-.+-auth-token$/.test(k)); } catch { /* Stockage bloqué. */ }
    try { this.badge(Number(sessionStorage.getItem('vp_events_pending')) || 0); } catch { /* Stockage bloqué. */ }
    if (!session) return;
    const start = () => { if (!document.getElementById('eventsFrame')?.hasAttribute('src')) this.open(); };
    if ('requestIdleCallback' in window) requestIdleCallback(start, { timeout: 4000 });
    else setTimeout(start, 1500);
  },
  /** Pastille sur l’onglet Événements et, si l’app est installée, sur son icône. */
  badge(count) {
    const n = Math.max(0, Math.min(99, Number(count) || 0));
    document.querySelectorAll('[data-events-badge]').forEach((el) => {
      el.textContent = String(n);
      el.classList.toggle('hidden', n === 0);
      el.closest('button')?.setAttribute('aria-label', n ? `Événements, ${n} sortie${n > 1 ? 's' : ''} en attente de ta réponse` : 'Événements');
    });
    try { sessionStorage.setItem('vp_events_pending', String(n)); } catch { /* Stockage bloqué. */ }
    try {
      if (n && navigator.setAppBadge) navigator.setAppBadge(n).catch(() => {});
      else if (!n && navigator.clearAppBadge) navigator.clearAppBadge().catch(() => {});
    } catch { /* Non pris en charge. */ }
  },
};

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.data?.type !== 'party-events:pending') return;
  window.PartyEvents.badge(event.data.count);
});
