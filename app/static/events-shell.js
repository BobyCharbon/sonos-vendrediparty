// Pont de navigation commun aux pages invités et admin. Aucune donnée de compte ici.
// En production (data-events="beta"), les sorties ne s'ouvrent qu'aux bêta-testeurs ; le compte Party reste ouvert à tous.
const betaOnly = document.documentElement.dataset.events === 'beta';
let betaTester = false;
try { betaTester = !!JSON.parse(localStorage.getItem('vp_account') || 'null')?.beta; } catch { /* Stockage bloqué. */ }
window.PartyEvents = {
  /** Pas (encore) bêta-testeur : l'onglet affiche « Bientôt » et les sorties ne sont pas chargées. */
  get soon() { return betaOnly && !betaTester; },
  /** Résultat de la liaison du compte Party (ou false à la déconnexion). */
  setBeta(on) {
    const changed = betaTester !== !!on;
    betaTester = !!on;
    markSoon();
    // Le module déjà ouvert relit aussitôt ses droits (sinon il garderait « Bientôt » ou les sorties).
    if (changed) {
      try { document.getElementById('eventsFrame')?.contentWindow?.postMessage({ type: 'party-shell:refresh' }, location.origin); } catch { /* Cadre pas encore chargé. */ }
    }
  },
  target(params, admin = false) {
    const id = params.get('event') || '';
    if (/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(id)) return '/events/event/' + id;
    if (params.get('activity') === '1') return '/events/activity';
    return admin ? '/events/admin' : '/events/';
  },
  open(target) {
    if (this.soon) return;
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
    if (this.soon) return;
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
 * Le module va jusqu’en haut de l’écran : il reçoit la marge du haut et celles des côtés ;
 * la barre d’onglets de Party gère le bas.
 */
window.PartyEvents.frameInsets = function frameInsets() {
  const none = { top: 0, right: 0, bottom: 0, left: 0 };
  if (!document.body) return none;
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
// Hauteur réelle de la barre d’onglets (barre d’accueil comprise) : le module s’arrête pile au-dessus.
function measureTabs() {
  const tabs = document.getElementById('tabs');
  if (tabs) document.documentElement.style.setProperty('--tabs-h', `${Math.round(tabs.getBoundingClientRect().height)}px`);
}
function watchTabs() {
  measureTabs();
  const tabs = document.getElementById('tabs');
  if (tabs && 'ResizeObserver' in window) new ResizeObserver(measureTabs).observe(tabs);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchTabs, { once: true });
else watchTabs();
// Rotation, changement de taille : le module relit ses marges.
['resize', 'orientationchange'].forEach((type) => window.addEventListener(type, () => {
  measureTabs();
  const frame = document.getElementById('eventsFrame');
  try { frame?.contentWindow?.postMessage({ type: 'party-shell:insets' }, location.origin); } catch { /* Cadre pas encore chargé. */ }
}));

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.data?.type !== 'party-events:pending') return;
  window.PartyEvents.badge(event.data.count);
});

// « Bientôt » : l'onglet reste visible mais n'ouvre rien (annoncé aux lecteurs d'écran).
function markSoon() {
  const soon = window.PartyEvents.soon;
  document.documentElement.classList.toggle('events-soon', soon);
  if (soon) window.PartyEvents.badge(0);  // avant l'étiquette : la pastille réécrit aria-label
  document.querySelectorAll('[data-tab="events"]').forEach((b) => {
    if (soon) {
      b.setAttribute('aria-disabled', 'true');
      b.setAttribute('aria-label', 'Événements : bientôt disponible');
    } else if (b.getAttribute('aria-disabled')) {
      b.removeAttribute('aria-disabled');
      b.setAttribute('aria-label', 'Événements');
    }
  });
}
document.documentElement.classList.toggle('events-soon', window.PartyEvents.soon);  // dès le chargement, sans clignoter
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', markSoon); else markSoon();
