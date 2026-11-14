"""Noms piégés partout (campagne sécurité du 14.11.2026) : un prénom, un titre ou un message tapé par quelqu'un ne
devient jamais du code dans la page — jeux, page Party, admin, TV, annonce pour tout le monde.

Vrai navigateur, vrai serveur : des joueurs aux prénoms piégés (« <img src=x onerror=…> », « "><img … »,
« " onfocus=… x=" ») lancent chaque jeu ; on regarde la page de l'animateur, celle d'un joueur, l'admin et la TV.
Rien ne doit s'exécuter (window.__xss reste vide) et aucun élément ni attribut piégé ne doit exister dans le DOM."""
import json
import time
import uuid

import httpx
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect  # noqa: E402

from tests.e2e.helpers import ADMIN_PIN, DEVICES, Server  # noqa: E402

# 30 caractères au plus (prénom d'un joueur, app/main.py clean_name).
EVIL = ['<img src=x onerror=__x(1)>', '"><img src=x onerror=__x(2)>', '" onfocus=__x(3) autofocus x="',
        "'><img src=x onerror=__x(4)>"]
TRAP = 'window.__xss = []; window.__x = (n) => window.__xss.push(n);'
# Ce qui trahit une injection : le code a tourné, une image « x » existe, ou un attribut on… porte notre appel.
FOUND = """() => {
  const docs = [document, ...[...document.querySelectorAll('iframe')].map((f) => { try { return f.contentDocument; } catch { return null; } })];
  const out = { fired: [...(window.__xss || [])], nodes: [] };
  for (const d of docs.filter(Boolean)) {
    for (const el of d.querySelectorAll('*')) {
      if (el.tagName === 'IMG' && el.getAttribute('src') === 'x') out.nodes.push('img src=x');
      for (const a of el.attributes) {
        if (/^on/i.test(a.name) && a.value.includes('__x')) out.nodes.push(`${el.tagName} ${a.name}=${a.value}`);
        if (/^(href|src|action|formaction)$/i.test(a.name) && /^\\s*javascript:/i.test(a.value)) out.nodes.push(`${el.tagName} ${a.name}=${a.value}`);
      }
    }
  }
  return out;
}"""

# Jeux lancés à trois (3D exclue : L'île et le Braquage ont leurs propres tests ; Purify Test exige un compte).
GAMES = ['undercover', 'whoof', 'likely', 'debate', 'beerpong', 'never', 'roulette', 'blackjack', 'casino', 'divan',
         'tmc', 'pyramid', 'biskit', 'quiz', 'president', 'neon', 'psy', 'masque', 'reflet', 'room']


def clean(found):
    return not found['fired'] and not found['nodes']


@pytest.fixture
def server():
    s = Server(compagnon=False)
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


def player(server, name):
    return {'guest_id': f'xss-{uuid.uuid4().hex[:12]}', 'name': name}


def act(server, code, who, action, **extra):
    return httpx.post(f'{server.url}/api/games/{code}', json={**who, 'action': action, **extra}, timeout=10)


def phone(browser, server, who, device='iphone'):
    ctx = browser.new_context(base_url=server.url, locale='fr-CH', **DEVICES[device])
    ctx.add_init_script(TRAP + f"""
        if (!localStorage.getItem('vp_guest')) {{
          localStorage.setItem('vp_guest', {json.dumps(who['guest_id'])});
          localStorage.setItem('vp_name', {json.dumps(who['name'])});
          localStorage.setItem('vp_install_dismissed', '1');
        }}""")
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(f'exception JS : {e}'))
    page.on('dialog', lambda d: (errors.append(f'boîte de dialogue : {d.message}'), d.dismiss()))
    return ctx, page, errors


def settle(page, ms=1600):
    page.wait_for_timeout(ms)
    return page.evaluate(FOUND)


def test_trapped_names_never_run_in_any_game_nor_in_the_admin_or_tv(browser, server):
    host, b, c, d = (player(server, n) for n in EVIL)
    codes = {}
    for kind in GAMES:
        r = httpx.post(f'{server.url}/api/games', json={**host, 'type': kind}, timeout=10)
        assert r.status_code == 200, (kind, r.text)
        code = r.json()['code']
        codes[kind] = code
        for who in (b, c, d):
            act(server, code, who, 'join')
        # Un joueur sans téléphone, au nom piégé lui aussi (jeux qui l'acceptent).
        act(server, code, host, 'add', name=EVIL[1])

    hctx, hpage, herr = phone(browser, server, host)
    pctx, ppage, perr = phone(browser, server, b, 'android')
    problems = []
    try:
        for kind, code in codes.items():
            for when in ('salle d’attente', 'partie lancée'):
                for label, page in (('animateur', hpage), ('joueur', ppage)):
                    page.goto(f'/?game={code}')
                    expect(page.locator('#gamePlay')).to_be_visible()
                    found = settle(page)
                    if label == 'animateur' and when == 'salle d’attente':
                        found['shown'] = page.locator('#gamePlay').inner_text().count(EVIL[0])
                        if not found['shown']:
                            problems.append((kind, 'prénom piégé absent de la salle d’attente', found))
                    if not clean(found):
                        problems.append((kind, when, label, found))
                if when == 'salle d’attente':
                    act(server, code, host, 'start')
        # Admin de la soirée : liste des parties et des joueurs ; TV : partie en cours.
        actx, apage, aerr = phone(browser, server, host, 'desktop')
        try:
            apage.request.post(f'{server.url}/api/admin/login', data={'pin': ADMIN_PIN})
            for path in ('/admin#games', '/admin#settings', '/tv'):
                apage.goto(path)
                found = settle(apage, 2500)
                if not clean(found):
                    problems.append((path, '', 'admin', found))
            herr += aerr
        finally:
            actx.close()
    finally:
        hctx.close(); pctx.close()
    assert not problems, '\n'.join(map(str, problems))
    assert not herr and not perr, '\n'.join(herr + perr)


def test_trapped_notice_is_plain_text_for_guests_and_admin(browser, server):
    admin = httpx.Client(base_url=server.url, timeout=10)
    assert admin.post('/api/admin/login', json={'pin': ADMIN_PIN}).status_code == 200
    r = admin.post('/api/admin/notice', json={'kind': 'announce', 'title': EVIL[0], 'message': EVIL[1] + '\n' + EVIL[2]})
    assert r.status_code == 200, r.text
    who = player(server, 'Alice')
    ctx, page, errors = phone(browser, server, who)
    try:
        page.goto('/')
        expect(page.locator('#partyNotice')).to_contain_text(EVIL[0])
        assert clean(settle(page, 800)), page.evaluate(FOUND)
        page.request.post(f'{server.url}/api/admin/login', data={'pin': ADMIN_PIN})
        page.goto('/admin#settings')
        assert clean(settle(page, 2000)), page.evaluate(FOUND)
    finally:
        ctx.close()
    assert not errors, '\n'.join(errors)
