"""QA Méninges, zone « jeux B » : Aiguillages, Mot ou encre, Bascule, Contre-courant, Plus lourd, Gouttes, Débuts de
mots, joués dans le VRAI moteur (core.js : 3 vies, paliers, HUD, écran de fin) par des robots qui répondent d'après ce qui
est AFFICHÉ (tests/e2e/qa_jeux_b_robot.js, évaluateur de calculs indépendant des jeux), avec de vrais événements
(toucher : la cible doit être visible à l'écran ; clavier : flèches, chiffres, Entrée). Horloge simulée.

- robot parfait : dépasse le niveau 60 sans perdre une vie, jamais de fin, rien d'impossible ;
- départ au palier max débloqué (choix sur l'écran d'explication), jusqu'au palier 20 ;
- joueur passif : perd ses 3 vies, écran de fin, plus rien ne tourne (aucun minuteur, aucune image, aucun écouteur) ;
- erreurs occasionnelles : la partie finit ; relances multiples sans fuite ;
- iPhone 390 × 844, iPad, paysage 844 × 390 (toutes les commandes restent à l'écran), mouvement réduit ;
- justesse de tous les calculs de Plus lourd et Gouttes (milliers de questions, tous niveaux) ;
- Aiguillages : réseaux valides de 2 à 10 gares, cibles ≥ 44 px ; équité (réponses Oui / Non équilibrées…)."""
import json
import math
import re
from pathlib import Path

import pytest
pytest.importorskip('playwright.sync_api')

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = 'http://qa.meninges.test'
ROBOT_JS = (Path(__file__).parent / 'qa_jeux_b_robot.js').read_text(encoding='utf-8')
TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.txt': 'text/plain; charset=utf-8',
         '.html': 'text/html'}
GAMES = ('aiguillage', 'encre', 'bascule', 'courant', 'balance', 'gouttes')
DEVICES = {
    'iphone': dict(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True),
    'ipad': dict(viewport={'width': 820, 'height': 1180}, device_scale_factor=2, is_mobile=True, has_touch=True),
    'paysage': dict(viewport={'width': 844, 'height': 390}, device_scale_factor=3, is_mobile=True, has_touch=True),
    'bureau': dict(viewport={'width': 1280, 'height': 800}),
}

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="stylesheet" href="/static/brain/brain.css?v=qa"></head>
<body style="margin:0;background:#000"><button type="button" data-brain-open>Méninges</button>
<script src="/static/brain/core.js?v=qa"></script></body></html>"""

# Compte des écouteurs, minuteurs et images en cours : une partie finie ne doit rien laisser derrière elle.
LEAK_PROBE = """(() => {
  const L = window.__leak = { listeners: new Map(), intervals: new Set(), timeouts: new Set(), raf: 0 };
  const add = EventTarget.prototype.addEventListener, rem = EventTarget.prototype.removeEventListener;
  const name = (t) => t === window ? 'window' : t === document ? 'document' : null;
  EventTarget.prototype.addEventListener = function (type, fn, opt) {
    const n = name(this);
    if (n && fn) { const k = n + ':' + type; if (!L.listeners.has(k)) L.listeners.set(k, new Set()); L.listeners.get(k).add(fn); }
    return add.call(this, type, fn, opt);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, opt) {
    const n = name(this);
    if (n) L.listeners.get(n + ':' + type)?.delete(fn);
    return rem.call(this, type, fn, opt);
  };
  const si = window.setInterval, ci = window.clearInterval, st = window.setTimeout, ct = window.clearTimeout;
  window.setInterval = function (f, ms, ...a) { const id = si(f, ms, ...a); L.intervals.add(id); return id; };
  window.clearInterval = function (id) { L.intervals.delete(id); return ci(id); };
  window.setTimeout = function (f, ms, ...a) { const id = st(function () { L.timeouts.delete(id); return typeof f === 'function' ? f.apply(this, arguments) : undefined; }, ms, ...a); L.timeouts.add(id); return id; };
  window.clearTimeout = function (id) { L.timeouts.delete(id); return ct(id); };
  const raf = window.requestAnimationFrame;
  window.requestAnimationFrame = function (f) { L.raf++; return raf(f); };
  window.__leakCount = () => ({ listeners: [...L.listeners].filter(([, s]) => s.size).map(([k, s]) => k + '×' + s.size).sort(),
    intervals: L.intervals.size, timeouts: L.timeouts.size, raf: L.raf });
})();"""


def _serve(route):
    url = route.request.url
    path = url.removeprefix(ORIGIN).split('?')[0]
    if path.startswith('/static/'):
        file = ROOT / 'app' / path.lstrip('/')
        if not file.is_file():
            return route.fulfill(status=404, body='absent')
        return route.fulfill(path=str(file), content_type=TYPES.get(file.suffix, 'application/octet-stream'))
    if path.startswith('/api/brain/'):
        return route.fulfill(body='{}', content_type='application/json')
    return route.fulfill(body=PAGE, content_type='text/html')


class Bench:
    """Un téléphone (contexte navigateur) qui joue aux Méninges avec le vrai moteur."""

    def __init__(self, browser, device='iphone', reduced=False):
        self.ctx = browser.new_context(**DEVICES[device], reduced_motion='reduce' if reduced else 'no-preference')
        self.page = self.ctx.new_page()
        self.errors = []
        self.page.on('console', lambda m: m.type in ('error', 'warning') and self.errors.append(f'{m.type}: {m.text}'))
        self.page.on('pageerror', lambda e: self.errors.append(f'pageerror: {e}'))
        self.page.route(f'{ORIGIN}/**', _serve)
        self.page.add_init_script(LEAK_PROBE)
        self.page.clock.install()
        self.page.goto(f'{ORIGIN}/qa')
        self.page.add_script_tag(content=ROBOT_JS)

    def open_home(self):
        self.page.evaluate('Brain.open()')
        self.page.wait_for_selector('#brainRoot .br-home', timeout=15000)

    def start(self, game, mode='parfait', input='touch', tier=None, rt=280):
        """Accueil → explication (palier de départ) → 3-2-1 → partie, puis le robot."""
        page = self.page
        if tier:
            page.evaluate('([g, t]) => localStorage.setItem("brain_tiers", JSON.stringify({[g]: t}))', [game, tier])
        if page.evaluate("!document.querySelector('#brainRoot .br-home, #brainRoot .br-end')"):
            self.open_home()
        page.evaluate("(g) => document.querySelector(`#brainRoot [data-br=\"play\"][data-id=\"${g}\"], #brainRoot [data-br=\"again\"]`).click()", game)
        page.wait_for_selector('#brainRoot .br-howto')
        if tier:
            label = page.inner_text('#brainRoot .br-tier b' if tier > 1 else '#brainRoot .br-tier')
            assert label.startswith(f'Départ : palier {tier}'), label
        page.click('#brainRoot [data-br="go"]')
        page.clock.run_for(2600)
        page.wait_for_selector('#brainRoot .br-hud')
        page.evaluate('([g, o]) => qaRobot(g, o)', [game, {'mode': mode, 'input': input, 'rt': rt}])

    def qa(self):
        return self.page.evaluate('({...__qa, truths: undefined, typed: undefined, ntruths: __qa.truths.length})')

    def screen(self):
        return self.page.evaluate("document.querySelector('#brainRoot')?.dataset.screen || null")

    def play(self, seconds, until_level=None, step=4):
        for _ in range(int(seconds / step)):
            self.page.clock.run_for(step * 1000)
            q = self.qa()
            if self.screen() != 'play' or (until_level and q['maxLevel'] >= until_level):
                break
        return self.qa()

    def close(self):
        self.ctx.close()


@pytest.fixture
def bench(browser):
    made = []

    def make(device='iphone', reduced=False):
        b = Bench(browser, device, reduced)
        made.append(b)
        return b

    yield make
    errors = [e for b in made for e in b.errors]
    for b in made:
        b.close()
    assert not errors, '\n'.join(errors[:20])


def assert_clean_run(q, label=''):
    assert not q['errors'], f'{label} erreur du robot : {q["errors"][:3]}'
    assert not q['mismatch'], f'{label} affichage incohérent : {q["mismatch"][:5]}'
    assert not q['blocked'], f'{label} cible hors écran ou cachée : {q["blocked"][:5]}'


# ── Robot parfait : niveau 60+, jamais de vie perdue ──

@pytest.mark.parametrize('inp', ['touch', 'key'])
@pytest.mark.parametrize('game', GAMES)
def test_perfect_robot_climbs_past_level_60_without_losing_a_life(bench, game, inp):
    if game == 'aiguillage' and inp == 'key':
        pytest.skip('Aiguillages se joue au toucher seulement')
    b = bench('iphone' if inp == 'touch' else 'bureau')
    b.start(game, 'parfait', inp)
    q = b.play(30 * 60, until_level=61)
    assert_clean_run(q, game)
    assert b.screen() == 'play', f'{game} : la partie a fini (robot parfait) {q}'
    assert q['minLives'] == 3, f'{game} : vie perdue par un robot parfait {q}'
    assert q['maxLevel'] >= 61, f'{game} : niveau {q["maxLevel"]} seulement'
    truths = b.page.evaluate('__qa.truths')
    assert_fair(game, truths)


def assert_fair(game, truths):
    """Équité : les bonnes réponses ne sont pas prévisibles (Oui / Non, directions, côtés équilibrés)."""
    if game in ('encre', 'bascule'):
        assert len(truths) > 300 and 0.4 <= sum(truths) / len(truths) <= 0.6, (game, len(truths), sum(truths))
    elif game == 'courant':
        assert len(truths) > 200 and all(0.15 <= truths.count(d) / len(truths) <= 0.35 for d in range(4)), truths[:40]
    elif game == 'balance':
        assert len(truths) > 150 and 0.1 <= truths.count(0) / len(truths) <= 0.32
        assert abs(truths.count(1) - truths.count(-1)) / len(truths) < 0.15


# ── Justesse des calculs : milliers de questions à chaque niveau (banc à contexte simulé, réponses synchrones) ──

CALC_BENCH = """<!doctype html><html lang="fr"><head><meta charset="utf-8"></head><body><div id="root"></div><script>
var defs = {}; window.Brain = {register: function (d) { defs[d.id] = d; }};
var frames = []; window.requestAnimationFrame = function (f) { frames.push(f); return frames.length; };
window.cancelAnimationFrame = function () {};
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
window.qaCalc = function (id, level, seed) {
  var out = {hit: 0, miss: 0, slip: 0};
  var box = document.getElementById('root'); box.innerHTML = '';
  var host = document.createElement('div'); host.style.cssText = 'width:390px;height:640px;display:flex;flex-direction:column';
  box.appendChild(host);
  var ctx = {root: host, level: level, rng: mulberry32(seed), reducedMotion: true, lives: 3,
    hit: function () { out.hit++; }, miss: function () { out.miss++; }, slip: function () { out.slip++; },
    setLevel: function () {}, finish: function () {}, onTimeUp: function () {},
    esc: function (s) { return String(s); }};
  frames = [];
  var game = defs[id].start(ctx);
  return {game: game, out: out};
};
</script>__SCRIPT__</body></html>"""

CALC_RUN = r"""([id, levels, seeds]) => {
  const rows = [], bad = [];
  for (const level of levels) for (let s = 1; s <= seeds; s++) {
    const {game, out} = qaCalc(id, level, level * 7919 + s);
    let text, truth;
    try {
      if (id === 'balance') {
        const L = document.querySelector('[data-side="l"]').textContent, R = document.querySelector('[data-side="r"]').textContent;
        const a = qaEvaluate(L), b = qaEvaluate(R);
        truth = Math.abs(a - b) < 1e-9 ? 0 : a > b ? 1 : -1;
        text = `${L} | ${R}`;
        document.querySelector(`[data-answer="${truth}"]`).click();
        rows.push([level, truth, Math.abs(a - b) / Math.max(a, b, 1e-9), L.length, R.length]);
      } else {
        const f = frames.shift(); f(16);
        const d = document.querySelector('.br-gouttes-drop');
        text = d.textContent; truth = qaEvaluate(text);
        for (const c of String(truth)) document.dispatchEvent(new KeyboardEvent('keydown', {key: c, bubbles: true}));
        document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
        rows.push([level, truth, 0, text.length, d.scrollHeight > d.clientHeight + 1 || d.scrollWidth > d.clientWidth + 1 ? 1 : 0]);
      }
    } catch (e) { bad.push(`${level}/${s} : ${e.message}`); }
    if (out.hit !== 1 || out.miss || out.slip) bad.push(`niveau ${level} : « ${text} » → ${truth}, jeu ${JSON.stringify(out)}`);
    game.stop();
  }
  return {rows, bad};
}"""


def _calc_serve(route):
    path = route.request.url.removeprefix(ORIGIN).split('?')[0]
    if path.startswith('/static/'):
        return _serve(route)
    game = route.request.url.split('id=')[-1]
    return route.fulfill(body=CALC_BENCH.replace('__SCRIPT__', f'<script src="/static/brain/games/{game}.js"></script>'),
                         content_type='text/html')


@pytest.mark.parametrize('game', ['balance', 'gouttes'])
def test_every_calculation_is_right_at_every_level(browser, game):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route(f'{ORIGIN}/**', _calc_serve)
    page.goto(f'{ORIGIN}/calc?id={game}')
    page.add_script_tag(content=ROBOT_JS)
    page.wait_for_function('Object.keys(defs).length > 0')
    result = page.evaluate(CALC_RUN, [game, list(range(1, 101)) + [120, 150, 200], 60])
    ctx.close()
    rows = result['rows']
    assert len(rows) >= 6000
    assert not errors, errors[:5]
    assert not result['bad'], f'{len(result["bad"])} calculs faux ou illisibles : ' + '\n'.join(result['bad'][:15])
    if game == 'balance':
        for lo, hi in ((1, 20), (21, 40), (41, 70), (71, 200)):
            part = [r for r in rows if lo <= r[0] <= hi]
            share = {k: sum(1 for r in part if r[1] == k) / len(part) for k in (1, 0, -1)}
            assert 0.1 <= share[0] <= 0.3 and abs(share[1] - share[-1]) < 0.12, (lo, hi, share)
    else:
        assert all(r[4] == 0 for r in rows), [r for r in rows if r[4]][:5]


# ── Aiguillages : réseaux valides pour chaque nombre de gares, paliers de 2 à 10 gares, cibles ≥ 44 px ──

TREES = r"""() => {
  const A = window.BrainAiguillage, bad = [];
  let count = 0;
  for (let n = 2; n <= 10; n++) for (let rows = A.depthNeeded(n); rows <= 7; rows++) for (const skew of [0, 0.3, 0.6, 0.9])
    for (let s = 1; s <= 120; s++) {
      count++;
      const rng = mulberry32(n * 100003 + rows * 1009 + s * 7 + Math.round(skew * 10));
      const tree = A.buildTree(n, rows, skew, rng), leaves = [], sw = [];
      A.walk(tree, (x) => (x.leaf ? leaves : sw).push(x));
      const tag = `n=${n} rangs=${rows} tordu=${skew} graine=${s}`;
      if (leaves.length !== n) bad.push(`${tag} : ${leaves.length} gares`);
      if (leaves.some((l, i) => l.slot !== i)) bad.push(`${tag} : gares dans le désordre`);
      if (sw.length !== n - 1) bad.push(`${tag} : ${sw.length} aiguillages`);
      if (Math.max(...sw.map((x) => x.depth)) + 1 > rows) bad.push(`${tag} : trop de rangs`);
      const first = (x) => (x.leaf ? x.slot : first(x.kids[0]));
      sw.forEach((x) => { if (x.split !== first(x.kids[1])) bad.push(`${tag} : aiguillage mal placé`); });
    }
  return {count, bad: bad.slice(0, 20)};
}"""


def test_aiguillage_networks_are_valid_for_every_station_count(browser):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.route(f'{ORIGIN}/**', _calc_serve)
    page.goto(f'{ORIGIN}/calc?id=aiguillage-niveaux')
    page.wait_for_function('window.BrainAiguillage')
    result = page.evaluate(TREES)
    ctx.close()
    assert result['count'] > 10_000 and not result['bad'], result['bad']


@pytest.mark.parametrize('device', ['iphone', 'ipad', 'paysage'])
def test_aiguillage_every_tier_has_its_stations_and_big_enough_targets(bench, device):
    b = bench(device)
    seen = {}
    for tier in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 20):
        b.start('aiguillage', 'parfait', tier=tier)
        b.page.clock.run_for(3000)
        q = b.qa()
        snap = q['snap']
        assert snap, f'palier {tier} : pas de réseau'
        assert snap['stations'] == min(10, tier + 1), (tier, snap)
        assert snap['hitRadius'] >= 22 and snap['minGap'] >= 44, (device, tier, snap)
        box = b.page.evaluate("(() => { const r = document.querySelector('canvas.br-aiguillage-canvas').getBoundingClientRect();"
                              " return [r.top, r.bottom, innerHeight]; })()")
        assert box[0] >= 0 and box[1] <= box[2] + 0.5, f'{device} palier {tier} : réseau coupé {box}'
        seen[tier] = snap
        b.page.evaluate("clearInterval(__qa.timer); document.querySelector('[data-br=\"quit\"]').click(); "
                        "document.querySelector('[data-br=\"leave\"]').click()")
        b.page.clock.run_for(200)
        b.page.wait_for_selector('#brainRoot .br-home')
    assert seen[10]['stations'] == seen[20]['stations'] == 10


# ── Écrans : iPad, paysage (toutes les commandes à l'écran), mouvement réduit ──

@pytest.mark.parametrize('setup', ['ipad', 'paysage', 'reduit'])
@pytest.mark.parametrize('game', GAMES)
def test_perfect_robot_plays_on_every_screen(bench, game, setup):
    b = bench('iphone' if setup == 'reduit' else setup, reduced=setup == 'reduit')
    b.start(game, 'parfait', 'touch', tier=8)
    q = b.play(150)
    assert_clean_run(q, f'{game}/{setup}')
    assert b.screen() == 'play' and q['minLives'] == 3, f'{game}/{setup} : vie perdue {q}'
    assert q['maxLevel'] > 36, q
    width = b.page.evaluate('[document.documentElement.scrollWidth, innerWidth]')
    assert width[0] <= width[1], f'{game}/{setup} : débordement horizontal {width}'
    stage = b.page.evaluate("(() => { const r = document.querySelector('#brStage').getBoundingClientRect(); "
                            "const s = document.querySelector('#brStage'); return [r.bottom, innerHeight, s.scrollHeight, s.clientHeight]; })()")
    assert stage[0] <= stage[1] + 0.5 and stage[2] <= stage[3] + 1, f'{game}/{setup} : le jeu dépasse de l\'écran {stage}'


# ── Joueur passif, erreurs occasionnelles, relances : la partie finit et ne laisse rien derrière elle ──

def _settled_leaks(b, seconds=8):
    """Après l'écran de fin : plus d'image demandée, plus de minuteur, écouteurs revenus à l'état de l'accueil."""
    b.page.clock.run_for(seconds * 1000)
    first = b.page.evaluate('__leakCount()')
    b.page.clock.run_for(5000)
    second = b.page.evaluate('__leakCount()')
    assert second['raf'] == first['raf'], 'une animation tourne encore après la fin'
    return second


def _end_now(b):
    b.page.evaluate('clearInterval(__qa.timer)')


@pytest.mark.parametrize('game', GAMES)
def test_passive_player_loses_three_lives_and_nothing_keeps_running(bench, game):
    b = bench()
    b.open_home()
    b.page.clock.run_for(500)
    base = b.page.evaluate('__leakCount()')
    b.start(game, 'passif')
    t0 = b.page.evaluate('performance.now()')
    q = b.play(120, step=1)
    took = (b.page.evaluate('performance.now()') - t0) / 1000
    assert b.screen() == 'end', f'{game} : toujours en jeu après {took:.0f} s sans rien faire'
    assert took < (45 if game in ('aiguillage', 'gouttes') else 25), f'{game} : {took:.0f} s pour perdre 3 vies'
    assert b.page.inner_text('#brainRoot .br-reason').startswith('💔')
    _end_now(b)
    after = _settled_leaks(b)
    assert after['listeners'] == base['listeners'], (base['listeners'], after['listeners'])
    assert after['intervals'] == base['intervals'], (base, after)


@pytest.mark.parametrize('game', GAMES)
def test_occasional_mistakes_end_the_game_and_replays_do_not_leak(bench, game):
    b = bench()
    b.open_home()
    b.page.clock.run_for(500)
    base = b.page.evaluate('__leakCount()')
    for n in range(3):    # trois parties de suite (« Rejouer »)
        b.start(game, 'errant', 'touch' if n % 2 == 0 else ('touch' if game == 'aiguillage' else 'key'))
        q = b.play(15 * 60, step=5)
        assert_clean_run(q, game)
        assert b.screen() == 'end', f'{game} partie {n + 1} : pas finie malgré une erreur sur cinq {q}'
        assert (q['acts'] >= 10 or game == 'aiguillage') and q['wrongOnPurpose'] >= 2, q
        _end_now(b)
        after = _settled_leaks(b, 3)
        assert after['listeners'] == base['listeners'], (n, base['listeners'], after['listeners'])
        assert after['intervals'] == base['intervals'], (n, base, after)
    stats = b.page.inner_text('#brainRoot .br-stats')
    assert 'Niveau max' in stats and 'Palier max' in stats


# ── Débuts de mots : vrai dictionnaire, 1 287 vrais mots et 209 faux tapés dans le jeu ──

DATA = ROOT / 'tests' / 'data'
MOTS = ROOT / 'app' / 'static' / 'brain' / 'mots'


def norm(word):
    import unicodedata
    w = word.lower().replace('œ', 'oe').replace('æ', 'ae')
    w = ''.join(c for c in unicodedata.normalize('NFD', w) if unicodedata.category(c) != 'Mn')
    return re.sub(r"[’‘ʼ´`]", "'", w)


def word_list(name):
    return [w for line in (DATA / f'qa_jeux_b_mots_{name}.txt').read_text(encoding='utf-8').splitlines()
            if not line.startswith('#') for w in line.split()]


def dico(prefix):
    file = MOTS / f'{prefix}.txt'
    return file.read_text(encoding='utf-8').split() if file.exists() else []


SYL_STATE = """() => { const i = document.querySelector('.br-syllabes-input');
  return i ? {playing: !i.disabled && !document.querySelector('.br-syllabes-send').disabled, prefix: document.querySelector('.br-syllabes-pre').textContent,
  manche: document.querySelector('.br-syllabes-rn').textContent, level: __qa.level, screen: document.querySelector('#brainRoot').dataset.screen,
  focused: document.activeElement === i} : {screen: document.querySelector('#brainRoot').dataset.screen}; }"""
# Saisie par le formulaire (même chemin que la touche Entrée / OK) ; s'arrête quand la manche est gagnée.
SYL_TYPE = """(items) => { const i = document.querySelector('.br-syllabes-input'), f = document.querySelector('.br-syllabes-form');
  const out = [];
  for (const [raw, kind] of items) {
    if (i.disabled || document.querySelector('.br-syllabes-send').disabled || f.dataset.qaRound !== undefined && f.dataset.qaRound !== document.querySelector('.br-syllabes-rn').textContent) break;
    f.dataset.qaRound = document.querySelector('.br-syllabes-rn').textContent;
    i.value = raw; f.requestSubmit();
    out.push([raw, kind, document.querySelector('.br-syllabes-note').textContent]);
  }
  delete f.dataset.qaRound;
  return out; }"""


def ios_forms(word, prefix, k):
    """Comme sur un iPhone : majuscule initiale, apostrophe typographique, point de la double espace, suite seule."""
    forms = [word, word[:1].upper() + word[1:], word + '. ', word.replace("'", '’').upper(), word]
    if norm(word[:3]) == prefix and len(word) > 4 and k % 5 == 4:
        return word[3:]
    return forms[k % 5]


def syllabes_index(prefixes):
    return json.dumps({'version': 'qa', 'total': 1, 'prefixes': {p: {'n': 999, 'common': 99, 'rank': 2} for p in prefixes}})


@pytest.fixture
def syl_bench(bench):
    def make(index=None, device='iphone'):
        b = bench(device)
        if index:
            b.page.route(f'{ORIGIN}/static/brain/mots/index.json*',
                         lambda route: route.fulfill(body=index, content_type='application/json'))
        return b
    return make


def test_syllabes_accepts_1287_real_words_and_refuses_209_fake_ones(syl_bench):
    """Chaque partie sert un index limité aux débuts qui restent à tester : chaque début sort une fois par partie."""
    # Débuts grossiers (con, cul, enc…) : jamais proposés comme lettres de départ (voulu) ; leurs mots ne se tapent pas ici.
    rude = {'con', 'cul', 'bit', 'put', 'nic', 'enc'}
    real = [w for w in word_list('vrais') if norm(w)[:3] not in rude]
    fake = [w for w in word_list('faux') if norm(w)[:3] not in rude]
    todo = {}
    for k, w in enumerate(real):
        todo.setdefault(norm(w)[:3], []).append((w, 'vrai', k))
    for k, w in enumerate(fake):
        todo.setdefault(norm(w)[:3], []).insert(0, (w, 'faux', k))
    results, games = [], 0
    while any(todo.values()) and games < 60:
        games += 1
        b = syl_bench(syllabes_index(sorted(p for p, v in todo.items() if v)))
        page = b.page
        b.start('syllabes', 'passif')
        manche = None
        for _ in range(400):
            page.clock.run_for(100)
            st = page.evaluate(SYL_STATE)
            if st['screen'] != 'play' or st.get('level', 0) >= 29:
                break
            if not st['playing'] or st['manche'] == manche:
                continue
            manche, prefix = st['manche'], st['prefix']
            mine = todo.get(prefix, [])
            if not mine:
                break                     # tous les débuts restants sont sortis : partie suivante
            keys = {norm(w) for w, _, _ in mine}
            filler = [w for w in dico(prefix) if len(w) >= 4 and w not in keys][:15]
            items = [[ios_forms(w, prefix, k), kind] for w, kind, k in mine] + [[w, 'remplissage'] for w in filler]
            done = page.evaluate(SYL_TYPE, items)
            typed = {raw for raw, _, _ in done}
            todo[prefix] = [m for m in mine if ios_forms(m[0], prefix, m[2]) not in typed]
            results += [r for r in done if r[1] != 'remplissage' or not re.search('Bien vu|Mot long|réussie', r[2])]
            page.clock.run_for(1650)      # pause entre les manches
        b.close()
    left = sum(len(v) for v in todo.values())
    assert left == 0, f'{left} mots pas encore tapés après {games} parties'
    wrong_real = [r for r in results if r[1] in ('vrai', 'remplissage') and not re.search('Bien vu|Mot long|réussie', r[2])]
    wrong_fake = [r for r in results if r[1] == 'faux' and 'mot inconnu' not in r[2]]
    assert not wrong_real, f'{len(wrong_real)} vrais mots refusés : {wrong_real[:20]}'
    assert not wrong_fake, f'{len(wrong_fake)} faux mots acceptés : {wrong_fake[:20]}'
    assert sum(1 for r in results if r[1] == 'vrai') == len(real) and sum(1 for r in results if r[1] == 'faux') == len(fake)


def test_syllabes_keyboard_stays_open_between_rounds_on_iphone(syl_bench):
    """Sur iPhone, un champ désactivé perd le focus (le clavier se ferme) et un focus() lancé par un minuteur ne le
    rouvre pas : entre deux manches, le champ doit rester actif et sélectionné, sinon il faut retoucher le champ à
    chaque manche (temps perdu sur le chrono de 30 s)."""
    b = syl_bench(syllabes_index(['cha', 'mai']))
    page = b.page
    b.start('syllabes', 'passif')
    page.clock.run_for(500)
    page.wait_for_function("!document.querySelector('.br-syllabes-input').disabled")
    page.tap('.br-syllabes-input')       # le joueur touche le champ une fois : le clavier s'ouvre
    for manche in (1, 2, 3):
        st = page.evaluate(SYL_STATE)
        assert st['playing'] and st['focused'], (manche, st)
        prefix = st['prefix']
        words = {'cha': ['Château', 'chaussette', 'Chaleur', 'chaîne', 'chapeaux', 'champignon'],
                 'mai': ['Maison', 'maïs', 'maître', 'maintenant', 'maigrir', 'mairie']}[prefix]
        goal = int(page.inner_text('.br-syllabes-goal').split('/')[1].split()[0])
        for w in words[:goal]:
            page.keyboard.type(w if manche != 2 else w[3:])
            page.keyboard.press('Enter')
        assert 'réussie' in page.inner_text('.br-syllabes-note'), (manche, prefix, page.inner_text('.br-syllabes-list'), page.inner_text('.br-syllabes-goal'))
        for _ in range(4):               # pause entre les manches : le clavier ne se ferme pas
            page.clock.run_for(400)
            st = page.evaluate(SYL_STATE)
            assert st['focused'], f'manche {manche} : le champ a perdu le focus pendant la pause (clavier fermé)'
        page.wait_for_function("document.querySelector('.br-syllabes-rn').textContent === 'Manche %d'" % (manche + 1))
    page.keyboard.type('chazzz')     # pendant la pause ou la manche : jamais de saisie perdue sans message
    page.keyboard.press('Enter')


def _syllabes_perfect(b, until_level, seconds):
    """Robot parfait de Débuts de mots : à chaque manche, des mots du vrai dictionnaire assez longs."""
    import random
    rnd = random.Random(5)
    page, manche, rounds = b.page, None, 0
    for _ in range(int(seconds / 0.4)):
        page.clock.run_for(400)
        st = page.evaluate(SYL_STATE)
        if st['screen'] != 'play' or st.get('level', 0) >= until_level:
            break
        if not st['playing'] or st['manche'] == manche:
            continue
        manche, rounds = st['manche'], rounds + 1
        min_len = page.evaluate('BrainSyllabes.minLenFor(__qa.level)')
        pool = [w for w in dico(st['prefix']) if len(w) >= min_len]
        assert len(pool) >= 12, f'début « {st["prefix"]} » : seulement {len(pool)} mots de {min_len} lettres et plus'
        page.clock.run_for(rnd.randint(300, 2000))
        done = page.evaluate(SYL_TYPE, [[w, 'vrai'] for w in rnd.sample(pool, 14)])
        refused = [d for d in done if not re.search('Bien vu|Mot long|réussie', d[2])]
        assert not refused, refused
    return rounds


@pytest.mark.parametrize('tier', [1, 12, 20])
def test_syllabes_perfect_player_never_runs_out_of_rounds(syl_bench, tier):
    b = syl_bench()
    b.start('syllabes', 'passif', tier=tier if tier > 1 else None)
    start = 1 + (tier - 1) * 5
    rounds = _syllabes_perfect(b, start + (12 if tier == 1 else 8), 900)   # plus de plafond à 99 (niveaux jusqu'à 999)
    q = b.qa()
    assert_clean_run(q, 'syllabes')
    assert b.screen() == 'play' and q['minLives'] == 3, q
    assert q['maxLevel'] >= start + (12 if tier == 1 else 8) and rounds >= 8, (q, rounds)


def test_syllabes_passive_player_loses_three_rounds_and_nothing_keeps_running(syl_bench):
    b = syl_bench()
    b.open_home()
    b.page.clock.run_for(500)
    base = b.page.evaluate('__leakCount()')
    b.start('syllabes', 'passif')
    for _ in range(150):
        b.page.clock.run_for(1000)
        if b.screen() != 'play':
            break
    assert b.screen() == 'end', 'Débuts de mots : toujours en jeu après 150 s sans rien taper'
    _end_now(b)
    after = _settled_leaks(b)
    assert after['listeners'] == base['listeners'] and after['intervals'] == base['intervals'], (base, after)
    assert b.page.evaluate("document.activeElement?.classList.contains('br-syllabes-input')") is not True


@pytest.mark.parametrize('game', GAMES)
def test_start_at_the_highest_tier_is_hard_but_playable(bench, game):
    """Palier 20 débloqué (niveau 96) : départ proposé au palier max, la partie reste jouable et monte au-delà du
    niveau 99 (paliers 21, 22… : plus de plafond à 99)."""
    b = bench()
    b.start(game, 'parfait', 'touch', tier=20)
    q = b.play(120)
    assert_clean_run(q, game)
    assert b.screen() == 'play' and q['minLives'] == 3, f'{game} au palier 20 : {q}'
    tier = int(b.page.inner_text('#brainRoot .br-lvl').rsplit(' ', 1)[1])
    assert q['level'] >= 96 and tier >= 20, q


@pytest.mark.parametrize('game', GAMES)
def test_turning_the_phone_mid_game_keeps_everything_playable(bench, game):
    """Portrait → paysage → portrait en pleine partie (palier 6) : rien de coupé, aucune vie perdue."""
    b = bench()
    b.start(game, 'parfait', 'touch', tier=6)
    for size in ({'width': 844, 'height': 390}, {'width': 390, 'height': 844}, {'width': 844, 'height': 390}):
        b.play(24)
        b.page.set_viewport_size(size)
    q = b.play(24)
    assert_clean_run(q, game)
    assert b.screen() == 'play' and q['minLives'] == 3, f'{game} : vie perdue en tournant le téléphone {q}'


@pytest.mark.parametrize('game', GAMES)
def test_real_touches_from_the_browser_play_every_game(bench, game):
    """Vrais touchers Playwright (touchscreen.tap ; glissé à la souris pour Contre-courant) : 40 s sans faute."""
    b = bench('iphone' if game != 'courant' else 'bureau')
    b.start(game, 'parfait', 'reel', tier=4)
    page, done = b.page, 0
    for _ in range(800):
        page.clock.run_for(50)
        for act in page.evaluate('__qa.queue.splice(0)'):
            done += 1
            if act[0] == 'tap':
                page.touchscreen.tap(act[1], act[2])
            else:
                page.mouse.move(act[1], act[2])
                page.mouse.down()
                page.mouse.move(act[3], act[4], steps=4)
                page.mouse.up()
    q = b.qa()
    assert_clean_run(q, game)
    assert done >= 10 and b.screen() == 'play' and q['minLives'] == 3, (done, q)
    assert q['maxLevel'] > 16, q
