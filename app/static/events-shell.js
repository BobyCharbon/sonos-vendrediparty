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

/**
 * Marges de sécurité à appliquer DANS le module (encoche, Dynamic Island, bords arrondis).
 * Sur la page invités (coque d’app), le module va jusqu’en haut de l’écran : il reçoit la
 * marge du haut et celles des côtés ; la barre d’onglets de Party gère le bas.
 * Ailleurs (admin), le cadre est déjà décalé : rien à ajouter.
 */
window.PartyEvents.frameInsets = function frameInsets() {
  const none = { top: 0, right: 0, bottom: 0, left: 0 };
  if (!document.body?.classList.contains('shell')) return none;
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;'
    + 'padding:env(safe-area-inset-top) env(safe-area-inset-right) 0 env(safe-area-inset-left)';
  document.body.append(probe);
  const cs = getComputedStyle(probe);
  const rail = matchMedia('(min-width: 900px)').matches;  // rail d’onglets à gauche
  const insets = {
    top: parseFloat(cs.paddingTop) || 0,
    right: parseFloat(cs.paddingRight) || 0,
    bottom: 0,
    left: rail ? 0 : parseFloat(cs.paddingLeft) || 0,
  };
  probe.remove();
  return insets;
};
// Rotation, changement de taille : le module relit ses marges.
['resize', 'orientationchange'].forEach((type) => window.addEventListener(type, () => {
  const frame = document.getElementById('eventsFrame');
  try { frame?.contentWindow?.postMessage({ type: 'party-shell:insets' }, location.origin); } catch { /* Cadre pas encore chargé. */ }
}));

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.data?.type !== 'party-events:pending') return;
  window.PartyEvents.badge(event.data.count);
});
