"""Lisibilité du module Événements à 375 px (audit graphique du 14.11.2026), vrai navigateur, Supabase simulé :
- fiche : aucun texte sous 12 px (sauf initiales d'avatar), contraste WCAG AA (4.5:1) partout, l'heure d'une réponse
  reste entière à côté d'un long nom, le nom d'un lien envoyé n'est plus réduit à « Lien pou… », un surnom de
  12 caractères larges (« WWWWWWWWWWWW ») tient dans la carte Invités ;
- accueil : pastilles rouges (cloche, « Sondages ») lisibles ; étape 2 de « Créer avec l'IA » : étapes et liens lisibles ;
- onglets de Party : la pastille « Événements » est lisible (12 px, 4.5:1)."""
import base64
import json
import re
import time
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_events_browser import DIST, EVENT, USER, browser, pw  # noqa: F401
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

def built_host() -> str:
    """Base Supabase compilée dans le module (production par défaut, TEST si construit pour elle) : tout y est simulé."""
    for js in (DIST / '_expo/static/js/web').glob('entry-*.js'):
        found = re.search(r'https://[a-z]+\.supabase\.co', js.read_text(errors='ignore'))
        if found:
            return found.group(0)
    return 'https://gsuetixzobooggeaubvb.supabase.co'


HOST = built_host() if (DIST / 'index.html').exists() else 'https://gsuetixzobooggeaubvb.supabase.co'
REF = HOST.split('//')[1].split('.')[0]
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
P = [f'aaaaaaaa-0000-4000-8000-0000000000{i:02d}' for i in range(8)]
NAMES = ['WWWWWWWWWWWW', 'Léa', 'Marie-Thérèse de la Tour-Montagne', 'Tom', 'Zoé', 'Anaïs', 'Noé', 'Julien']
PROFILE = {'id': USER, 'display_name': 'Camille', 'phone': '41791234567', 'role': 'admin', 'status': 'active', 'avatar_url': None,
           'first_name': 'Camille', 'last_name': 'Démo', 'created_at': '2026-10-19T08:00:00Z'}
PERMS = ['events.view', 'events.rsvp', 'events.plus_ones', 'events.create', 'events.publish_direct', 'events.edit_own_published',
         'events.manage_all', 'events.see_participants', 'polls.create', 'chat.write']


def answer(user, status, at='2026-11-13T20:17:00Z'):
    return {'event_id': EVENT, 'user_id': user, 'status': status, 'waitlisted': False, 'plus_ones': 0, 'note': None, 'set_by': None, 'updated_at': at}


EVENT_ROW = {
    'id': EVENT, 'title': 'Raclette chez WWWWWWWWWWWW', 'description': '', 'created_by': USER, 'status': 'published', 'date_mode': 'fixed',
    'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'all_day': False, 'poll_deadline': None, 'members_can_propose_dates': True,
    'location_name': 'Chalet du Lac', 'location_address': None, 'location_url': None, 'price_chf': None, 'payment_info': None,
    'max_participants': None, 'waitlist_enabled': False, 'allow_plus_ones': False, 'max_plus_ones': 0, 'allow_maybe': True,
    'rsvp_deadline': None, 'visibility': 'invited', 'public_link': False, 'show_participants': True, 'pot_enabled': False,
    'tickets_enabled': False, 'carpool_enabled': False, 'forum_enabled': False, 'cover_url': None, 'category_id': None, 'category': None,
    'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'author': {'id': USER, 'display_name': 'Camille'},
    'event_tags': [], 'event_organizers': [], 'date_options': [], 'event_groups': [], 'reminders': [], 'bring_items': [],
    'polls': [{'id': 'p1', 'event_id': EVENT, 'question': 'Quel fromage ?', 'multiple_choice': False, 'anonymous': False,
               'members_can_add_options': True, 'results_after_vote': False, 'closes_at': None, 'created_by': USER, 'sort': 0,
               'poll_options': [{'id': 'o1', 'poll_id': 'p1', 'label': 'Vacherin', 'sort': 0}]}],
    'rsvps': [answer(P[0], 'yes'), answer(P[2], 'yes', '2026-11-10T09:00:00Z'), answer(P[1], 'maybe'), answer(P[3], 'no')],
}
GUESTS = {'vip': False, 'public': False, 'vip_name': 'Vendredi Party', 'groups': [],
          'people': [{'id': P[i], 'name': NAMES[i], 'avatar_url': None, 'status': s, 'waitlisted': False, 'plus_ones': 0, 'source': 'person',
                      'group': None, 'invited_by': 'Camille', 'invited_by_id': USER, 'link_label': None, 'link_token': None, 'has_app': True,
                      'light': False, 'nudged_today': False, 'removable': True} for i, s in enumerate(['yes', 'maybe', 'yes', 'no'])],
          'links': [{'token': 'tok1', 'label': 'WWWWWWWWWWWW', 'max_uses': 1, 'uses': 0, 'created_at': '2030-11-01T10:00:00Z',
                     'expires_at': '2030-11-15T10:00:00Z', 'opened_at': None, 'state': 'pending', 'version': 2, 'created_by': 'Camille',
                     'created_by_id': USER, 'nudged_today': False, 'arrivals': []}]}
NOTIFS = [{'id': 'n1', 'kind': 'poll_new', 'title': 'Nouveau sondage', 'body': 'Fondue', 'event_id': EVENT, 'created_at': '2026-11-13T10:00:00Z',
           'read_at': None}]

# Pour chaque texte visible : taille, contraste (fond réel, couches translucides comprises), texte coupé.
AUDIT = """() => {
  const parse = (s) => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const blend = (t, u) => [0, 1, 2].map((i) => t[i] * t[3] + u[i] * (1 - t[3])).concat(1);
  const out = { contrast: [], small: [], cut: [] };
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden') continue;
    if (![...el.childNodes].some((n) => n.nodeType === 3 && /[A-Za-zÀ-ÿ0-9]/.test(n.textContent))) continue;
    let disabled = false; const layers = []; let opacity = 1;
    for (let p = el; p; p = p.parentElement) {
      if (p.getAttribute('aria-disabled') === 'true') disabled = true;
      const s = getComputedStyle(p); opacity *= Number(s.opacity);
      const c = parse(s.backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    let bg = [21, 16, 42, 1]; for (let i = layers.length - 1; i >= 0; i--) bg = blend(layers[i], bg);
    const fg = parse(cs.color); const fgB = blend([fg[0], fg[1], fg[2], fg[3] * opacity], bg);
    const l1 = lum(fgB), l2 = lum(bg); const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const size = parseFloat(cs.fontSize); const large = size >= 24 || (size >= 18.66 && Number(cs.fontWeight) >= 700);
    const text = el.innerText.trim().replace(/\\s+/g, ' ').slice(0, 60);
    if (!disabled && ratio < (large ? 3 : 4.5)) out.contrast.push(`${ratio.toFixed(2)} « ${text} »`);
    if (size < 12 && !/^[A-Z]{1,2}$/.test(text)) out.small.push(`${size}px « ${text} »`);
    if (cs.overflow === 'hidden' && el.scrollWidth > el.clientWidth + 1) out.cut.push(text);
  }
  return out;
}"""


def session_script():
    enc = lambda v: base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip('=')
    token = '.'.join([enc({'alg': 'HS256', 'typ': 'JWT'}), enc({'sub': USER, 'aud': 'authenticated', 'role': 'authenticated', 'exp': int(time.time()) + 3600}), 'sig'])
    session = {'access_token': token, 'refresh_token': 'r', 'expires_in': 3600, 'expires_at': int(time.time()) + 3600, 'token_type': 'bearer',
               'user': {'id': USER, 'aud': 'authenticated', 'phone': PROFILE['phone'], 'app_metadata': {}, 'user_metadata': {}, 'created_at': PROFILE['created_at']}}
    return f"localStorage.setItem('sb-{REF}-auth-token', {json.dumps(json.dumps(session))}); localStorage.setItem('party_module_alone', '1');"  # module seul : pas de renvoi vers Party


def open_page(browser, origin, path, event=EVENT_ROW):  # noqa: F811
    context = browser.new_context(viewport={'width': 375, 'height': 812}, is_mobile=True, has_touch=True, locale='fr-CH', timezone_id='Europe/Zurich')
    page = context.new_page()
    rpcs = {'get_member_directory': PROFILE, 'my_permissions': PERMS, 'my_rank': 99, 'event_group_names': [], 'event_guest_list': GUESTS,
            'my_terms': {'accepted': True, 'version': '2026-11-04'}}

    def handle(route):
        req = route.request
        if req.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        url = urlparse(req.url)
        name = url.path.rsplit('/', 1)[1]
        single = 'vnd.pgrst.object' in (req.headers.get('accept') or '')
        if '/rpc/' in url.path:
            body = rpcs.get(name)
        elif name == 'events':
            body = event if single else [event]
        elif name == 'profiles':
            body = [{'id': USER, 'display_name': 'Camille'}] + [{'id': p, 'display_name': n} for p, n in zip(P, NAMES)]
        elif name == 'notifications':
            rows = NOTIFS if 'read_at' in parse_qs(url.query) or req.method == 'GET' else []
            if req.method == 'HEAD':
                return route.fulfill(status=200, headers={**CORS, 'Access-Control-Expose-Headers': 'Content-Range', 'Content-Range': f'*/{len(NOTIFS)}'})
            body = rows
        else:
            body = {} if single else []
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=CORS)

    page.route(HOST + '/**', handle)
    page.route_web_socket(HOST.replace('https', 'wss') + '/**', lambda ws: ws.on_message(lambda _m: None))
    page.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(status=200, body=''))
    page.add_init_script(session_script())
    page.goto(origin + path, wait_until='domcontentloaded')
    return context, page


def test_event_page_is_readable_at_375_px(browser, v2_origin):  # noqa: F811
    context, page = open_page(browser, v2_origin, f'/events/event/{EVENT}')
    try:
        long_chip = page.get_by_role('button', name='Profil de Marie-Thérèse de la Tour-Montagne').first  # puce de « Qui vient ? »
        pw.expect(long_chip).to_be_visible(timeout=15000)
        # L'heure de la réponse reste entière (12 px) : c'est le nom qui se coupe.
        when = long_chip.get_by_text('10.11 · 10:00', exact=True)
        pw.expect(when).to_be_visible()
        assert when.evaluate('e => parseFloat(getComputedStyle(e).fontSize) >= 12 && e.scrollWidth <= e.clientWidth + 1')
        page.get_by_role('button', name='Voir le détail', exact=False).first.click()
        link_title = page.get_by_text('Lien pour WWWWWWWWWWWW', exact=True)
        pw.expect(link_title).to_be_visible(timeout=5000)
        assert link_title.evaluate('e => e.scrollWidth <= e.clientWidth + 1'), 'nom du lien coupé'
        guest = page.get_by_label('Invités', exact=True).get_by_text('WWWWWWWWWWWW', exact=True).first
        assert guest.evaluate('e => e.scrollWidth <= e.clientWidth + 1'), 'surnom de 12 caractères coupé'
        page.wait_for_timeout(800)  # fin des apparitions (fondus)
        found = page.evaluate(AUDIT)
        assert found['contrast'] == [], found['contrast']
        assert found['small'] == [], found['small']
    finally:
        context.close()


def test_home_badges_and_ai_step_two_are_readable(browser, v2_origin):  # noqa: F811
    context, page = open_page(browser, v2_origin, '/events/')
    try:
        bell = page.get_by_test_id('home-bell')
        pw.expect(bell).to_be_visible(timeout=15000)
        pw.expect(bell.get_by_text('1', exact=True)).to_be_visible(timeout=10000)
        page.wait_for_timeout(800)
        found = page.evaluate(AUDIT)
        assert [c for c in found['contrast'] if c.endswith('« 1 »')] == [], found['contrast']
        assert [s for s in found['small'] if s.endswith('« 1 »')] == [], found['small']
        draft = {**EVENT_ROW, 'status': 'draft', 'visibility': 'all', 'public_link': True, 'rsvps': [], 'polls': []}
        context.close()
        context, page = open_page(browser, v2_origin, f'/events/event/{EVENT}/invite', event=draft)
        steps = page.get_by_role('progressbar', name='Étape 2 sur 3 : Qui est invité')
        pw.expect(steps).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        found = page.evaluate(AUDIT)
        assert found['contrast'] == [], found['contrast']
        assert found['small'] == [], found['small']
        for label in ('La soirée', 'Qui est invité', 'C’est en ligne'):
            assert steps.get_by_text(label, exact=True).evaluate('e => e.scrollWidth <= e.clientWidth + 1'), f'étape coupée : {label}'
        # En-tête : « ‹ L'événement » touchait le titre centré (« L’événementQui est invité ») ; à 375 px, la flèche seule.
        back = page.get_by_role('button', name='Retour : L’événement')
        pw.expect(back).to_be_visible()
        assert back.bounding_box()['width'] < 60
        pw.expect(back.get_by_text('L’événement', exact=True)).to_have_count(0)
    finally:
        context.close()


def test_party_events_tab_badge_is_readable(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 375, 'height': 812})
    page = context.new_page()
    try:
        page.goto(v2_origin, wait_until='domcontentloaded')
        badge = page.locator('#tabs [data-events-badge]')
        badge.evaluate("e => { e.textContent = '3'; e.classList.remove('hidden'); }")
        size, ratio = badge.evaluate("""e => {
          const cs = getComputedStyle(e); const c = cs.backgroundColor.match(/\\d+/g).map(Number);
          const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
          const l = 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
          return [parseFloat(cs.fontSize), 1.05 / (l + 0.05)]; }""")
        assert size >= 12 and ratio >= 4.5, (size, ratio)
    finally:
        context.close()
