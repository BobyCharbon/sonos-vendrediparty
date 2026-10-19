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
};
