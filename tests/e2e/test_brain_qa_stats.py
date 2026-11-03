"""QA Méninges — statistiques (vrai navigateur). Réponses /api/brain/* et /api/account/card simulées (page.route) :
jamais joué, une partie, profil complet, champs null, nombres énormes, palier 20, 200 joueurs, noms très longs / emoji /
HTML piégé, historique vide ou de 365 jours, erreur serveur, réseau lent ; écrans 320 / 375 / 390 / 768 px et iPad,
thème sombre ou clair demandé par le système, animations réduites, contrastes WCAG AA, lecture VoiceOver (aria).

Deux surfaces : la fiche d'un membre (profile-card.js, comparaison Méninges) et Réglages → Mes stats de jeu (stats.js)."""
import json
import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.helpers import FakeSupabase, Phone, Server, sign_in

TOKEN = "jeton-de-test-guest-0001"
TRAP = '<img src=x onerror="window.__pwned=1">'
LONG = "Maximilienne-Antoinette-Bérénice de la Tour d'Auvergne 🧠🔥🎉" * 2
UNBROKEN = "W" * 80
DOMAINS = (("vitesse", "Vitesse", "⚡"), ("memoire", "Mémoire", "🧠"), ("attention", "Attention", "🎯"),
           ("flexibilite", "Flexibilité", "🔀"), ("logique", "Logique", "🧩"), ("calcul", "Calcul", "➗"))
GAMES = ("pareil", "motif", "autoroute", "grille", "deux_avant", "tresor", "nuee", "aiguillage",
         "intrus", "encre", "bascule", "courant", "balance", "gouttes", "syllabes")
WIDTHS = (320, 375, 390, 768)
IPAD = {"viewport": {"width": 820, "height": 1180}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True,
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"}
CARD = {"id": "u-bob", "display_name": "Bob", "role": "member", "root": False, "me": False, "first_name": None,
        "last_name": None, "phone": None, "groups": ["Vendredi"]}


# ── Données simulées ──

def target(name="Bob", played=True, me_played=True, temperature=1100, me_temperature=1250, rows=None, **extra) -> dict:
    if rows is None:
        rows = [{"domain": d, "label": lab, "icon": ico, "me": 1300 - 50 * i if me_played else None,
                 "them": 900 + 60 * i if played else None} for i, (d, lab, ico) in enumerate(DOMAINS)]
    return {"id": "u-bob", "name": name, "self": False, "played": played, "temperature": temperature if played else 0,
            "me_played": me_played, "me_temperature": me_temperature if me_played else 0, "rows": rows,
            "verdict": f"Ton point fort : Vitesse (+400 °M) ; celui de {name} : Calcul (+100 °M).", **extra}


def profile(plays=7, temperature=1240, history_days=12, level=6, tier=2, best=12450, index=1310) -> dict:
    games = {g: {"index": 0, "best": 0, "plays": 0, "last_level": 0, "max_level": 0, "max_tier": 0} for g in GAMES}
    if plays:
        games["pareil"] = {"index": index, "best": best, "plays": plays, "last_level": level, "max_level": level, "max_tier": tier}
    return {
        "name": "Méninges", "temperature": temperature,
        "domains": {d: {"index": index if d == "vitesse" else 0, "played": plays if d == "vitesse" else 0} for d, _, _ in DOMAINS},
        "games": games, "streak": {"current": 1, "best": 1},
        "history": [{"day": f"2026-{1 + (d // 28) % 12:02d}-{1 + d % 28:02d}", "temperature": 900 + d} for d in range(history_days)],
        "strengths": ["vitesse"], "weaknesses": [], "insight": "Ta force : Vitesse.", "percentile": 72,
        "speed_vs_accuracy": {"speed": 60, "accuracy": 55}, "month_progress": 12,
    }


def board(n=3, name=None) -> dict:
    players = [{"id": f"u-{i}", "name": name or f"Joueur {i}", "temperature": 2000 - i * 5, "me": i == 1} for i in range(n)]
    return {"board": players, "rank": 2, "players": n, "percentile": 72, "target": None}


# ── Montage ──

@pytest.fixture(scope="module")
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


@pytest.fixture
def make_phone(browser, server):
    phones = []

    def make(width=390, height=844, device=None, **ctx):
        p = Phone(browser, server, "Tom")
        if device or width != 390 or ctx:
            p.ctx.close()
            options = dict(device or {"viewport": {"width": width, "height": height}, "device_scale_factor": 2,
                                      "is_mobile": True, "has_touch": True})
            p.ctx = browser.new_context(base_url=server.url, locale="fr-CH", **options, **ctx)
            p.ctx.add_init_script("""localStorage.setItem("vp_guest", "e2e-tom-qa"); localStorage.setItem("vp_name", "Tom");
              localStorage.setItem("vp_install_dismissed", "1");""")
            p.page = p.ctx.new_page()
            p.page.on("pageerror", lambda e: p.errors.append(f"exception JS : {e}"))
            p.page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text
                      and "net::ERR" not in m.text and p.errors.append(f"console : {m.text}"))
        phones.append(p)
        return p
    yield make
    errors = [e for p in phones for e in p.errors]
    for p in phones:
        p.close()
    assert not server.errors(), server.errors()[-3000:]
    assert not errors, "\n".join(errors)


def json_route(data, status=200):
    def handler(route):
        if data is None:
            return route.abort()
        return route.fulfill(status=status, content_type="application/json", body=json.dumps(data))
    return handler


def signed_in(phone):
    phone.page.goto("/")
    sign_in(phone, TOKEN)
    phone.page.wait_for_function("account && account.name === 'Tom'")


def open_card(phone, compare, card=CARD, status=200):
    page = phone.page
    page.route("**/api/account/card", json_route(card))
    page.route("**/api/brain/compare", json_route(compare, status))
    signed_in(phone)
    page.evaluate("ProfileCard.open('1234', 'p-bob')")
    sheet = page.locator(".pc-card")
    expect(sheet.locator(".pc-name")).to_have_text(card["display_name"])
    return sheet


def no_horizontal_overflow(page, selector):
    """Aucun élément ne déborde de son conteneur à droite (texte coupé ou page qui défile de côté)."""
    over = page.evaluate("""(sel) => {
      const box = document.querySelector(sel).getBoundingClientRect();
      const bad = [];
      for (const el of document.querySelectorAll(sel + ' *')) {
        const r = el.getBoundingClientRect();
        if (r.width && (r.right > box.right + 1 || r.left < box.left - 1)) bad.push(el.className + ' ' + Math.round(r.right - box.right));
      }
      if (document.documentElement.scrollWidth > innerWidth + 1) bad.push('page ' + document.documentElement.scrollWidth);
      return bad;
    }""", selector)
    assert not over, over[:8]


def luminance(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb(css):
    return tuple(int(float(v)) for v in re.findall(r"[\d.]+", css)[:3])


# ════════════════ Fiche d'un membre : comparaison Méninges (profile-card.js) ════════════════

@pytest.mark.parametrize("width", WIDTHS)
def test_card_comparison_fits_every_phone_width_with_long_names_and_huge_numbers(make_phone, width):
    phone = make_phone(width=width, height=900)
    rows = [{"domain": d, "label": lab, "icon": ico, "me": 99999999, "them": -5} for d, lab, ico in DOMAINS]
    sheet = open_card(phone, {"target": target(name=LONG, temperature=123456789, me_temperature=2000, rows=rows)})
    expect(sheet.locator(".pc-brain-row")).to_have_count(7)
    no_horizontal_overflow(phone.page, ".pc-card")
    widths = phone.page.eval_on_selector_all(".pc-bar i", "els => els.map(e => e.style.width)")
    assert set(widths) <= {"100%", "0%"}, widths
    phone.shot(f"qa_card_brain_{width}")


def test_card_unbroken_name_does_not_push_the_card_sideways(make_phone):
    phone = make_phone(width=320, height=900)
    open_card(phone, {"target": target(name=UNBROKEN)})
    no_horizontal_overflow(phone.page, ".pc-card")


def test_card_numbers_are_formatted_like_the_stats_screen(make_phone):
    phone = make_phone()
    sheet = open_card(phone, {"target": target(temperature=1100, me_temperature=1250)})
    temp = sheet.locator(".pc-brain-row").first
    nbsp = phone.page.evaluate("(1250).toLocaleString('fr-CH')")
    expect(temp).to_contain_text(nbsp)


def test_card_trapped_name_and_verdict_are_escaped(make_phone):
    phone = make_phone()
    t = target(name=TRAP)
    t["verdict"] = TRAP
    t["rows"][0]["label"] = TRAP
    t["rows"][0]["icon"] = TRAP
    sheet = open_card(phone, {"target": t})
    expect(sheet.locator(".pc-brain")).to_contain_text(TRAP)
    expect(sheet.locator("img")).to_have_count(0)
    phone.page.wait_for_timeout(200)
    assert phone.page.evaluate("window.__pwned") is None


@pytest.mark.parametrize("case,expected", [
    ("never", "n'a pas encore joué"),
    ("me_never", "—"),
    ("self", None),
    ("null", None),
    ("rows_null", "Température"),
    ("no_rows", "Température"),
])
def test_card_edge_payloads(make_phone, case, expected):
    phone = make_phone()
    payload = {"never": target(played=False), "me_never": target(me_played=False), "self": {**target(), "self": True},
               "null": None, "rows_null": target(rows=None) | {"rows": None}, "no_rows": {k: v for k, v in target().items() if k != "rows"}}[case]
    sheet = open_card(phone, {"target": payload})
    phone.page.wait_for_timeout(400)
    if expected is None:
        expect(sheet.locator(".pc-brain")).to_have_count(0)
    else:
        expect(sheet.locator(".pc-brain")).to_contain_text(expected)


def test_card_server_error_keeps_the_card_without_comparison(make_phone):
    phone = make_phone()
    sheet = open_card(phone, {"detail": "Base indisponible"}, status=500)
    phone.page.wait_for_timeout(400)
    expect(sheet.locator(".pc-brain")).to_have_count(0)
    expect(sheet.locator(".pc-name")).to_have_text("Bob")


def test_card_slow_comparison_never_lands_on_another_members_card(make_phone):
    """Réseau lent : la comparaison de Bob arrive après qu'on a ouvert la fiche d'Alice (sans fermer) → pas chez Alice."""
    phone = make_phone()
    page = phone.page
    pending = []
    page.route("**/api/brain/compare", lambda route: pending.append(route))
    cards = {"p-bob": CARD, "p-alice": {**CARD, "id": "u-alice", "display_name": "Alice"}}
    page.route("**/api/account/card", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(cards[json.loads(route.request.post_data)["pid"]])))
    signed_in(phone)
    page.evaluate("ProfileCard.open('1234', 'p-bob')")
    expect(page.locator(".pc-name")).to_have_text("Bob")
    page.wait_for_function("() => true")
    page.evaluate("ProfileCard.open('1234', 'p-alice')")
    expect(page.locator(".pc-name")).to_have_text("Alice")
    page.wait_for_timeout(200)
    assert len(pending) == 2, pending
    pending[0].fulfill(status=200, content_type="application/json", body=json.dumps({"target": target(name="Bob")}))
    page.wait_for_timeout(300)
    expect(page.locator(".pc-brain")).to_have_count(0)
    pending[1].fulfill(status=200, content_type="application/json", body=json.dumps({"target": target(name="Alice")}))
    expect(page.locator(".pc-brain")).to_have_count(1)
    expect(page.locator(".pc-brain")).to_contain_text("Alice")


def test_card_closed_before_the_comparison_arrives(make_phone):
    phone = make_phone()
    page = phone.page
    pending = []
    page.route("**/api/brain/compare", lambda route: pending.append(route))
    page.route("**/api/account/card", json_route(CARD))
    signed_in(phone)
    page.evaluate("ProfileCard.open('1234', 'p-bob')")
    expect(page.locator(".pc-name")).to_have_text("Bob")
    page.locator(".pc-close").click()
    expect(page.locator(".pc-backdrop")).to_have_count(0)
    page.wait_for_timeout(100)
    pending[0].fulfill(status=200, content_type="application/json", body=json.dumps({"target": target()}))
    page.wait_for_timeout(300)
    expect(page.locator(".pc-brain")).to_have_count(0)


def test_card_voiceover_reads_who_is_who_on_each_row(make_phone):
    """VoiceOver : chaque ligne dit « toi … » et « Bob … », pas deux nombres sans contexte."""
    phone = make_phone()
    sheet = open_card(phone, {"target": target(me_played=False)})
    first = sheet.locator(".pc-brain-row").first
    label = first.locator("[role=img]").get_attribute("aria-label") or ""
    assert "toi" in label.lower() and "Bob" in label and "°M" in label, label
    assert "pas encore joué" in label, label
    expect(sheet.locator(".pc-bar").first).to_have_attribute("aria-hidden", "true")


def test_card_contrast_and_reduced_motion_and_light_scheme(make_phone):
    phone = make_phone(color_scheme="light", reduced_motion="reduce")
    sheet = open_card(phone, {"target": target()})
    expect(sheet.locator(".pc-brain")).to_be_visible()
    page = phone.page
    card_bg = rgb(page.eval_on_selector(".pc-card", "e => getComputedStyle(e).backgroundColor"))
    for sel in (".pc-brain-legend", ".pc-brain-label", ".pc-brain-bars b", ".pc-brain > p.artist", ".pc-brain-head"):
        fg = rgb(page.eval_on_selector(sel, "e => getComputedStyle(e).color"))
        assert contrast(fg, card_bg) >= 4.5, (sel, fg, card_bg, contrast(fg, card_bg))
    for sel in (".pc-bar.me i", ".pc-bar.them i"):
        fill = rgb(page.eval_on_selector(sel, "e => getComputedStyle(e).backgroundColor"))
        assert contrast(fill, card_bg) >= 3, (sel, fill)
    anim = page.eval_on_selector(".pc-card", "e => getComputedStyle(e).animationName")
    assert anim in ("fade-in", "none"), anim


def test_card_fits_a_small_screen_vertically(make_phone):
    """iPhone SE (320 × 568) : fiche complète (numéro, groupes, 7 lignes Méninges) — « Fermer » reste atteignable."""
    phone = make_phone(width=320, height=568)
    card = {**CARD, "phone": "41790000000", "first_name": "Robert", "last_name": "Dupont", "groups": ["Vendredi", "Famille", "Foot"]}
    sheet = open_card(phone, {"target": target()}, card=card)
    expect(sheet.locator(".pc-brain-row")).to_have_count(7)
    phone.page.wait_for_timeout(700)
    box = phone.page.eval_on_selector(".pc-card", "e => { const r = e.getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; }")
    phone.shot("qa_card_brain_se")
    assert box[0] >= 0 and box[1] <= box[2], f"fiche hors écran {box} : « Fermer » inatteignable, rien ne défile"
    close = sheet.locator(".pc-close")
    close.scroll_into_view_if_needed()
    expect(close).to_be_in_viewport()
    close.click()
    expect(phone.page.locator(".pc-backdrop")).to_have_count(0)


def test_card_on_ipad(make_phone):
    phone = make_phone(device=IPAD)
    sheet = open_card(phone, {"target": target(name=LONG)})
    expect(sheet.locator(".pc-brain-row")).to_have_count(7)
    no_horizontal_overflow(phone.page, ".pc-card")
    phone.shot("qa_card_brain_ipad")


# ════════════════ Réglages → Mes stats de jeu (stats.js) ════════════════

def open_stats(phone, me, board_data=None, status=200):
    page = phone.page
    page.route("**/api/brain/me", json_route(me, status))
    page.route("**/api/brain/compare", json_route(board_data if board_data is not None else board()))
    signed_in(phone)
    page.evaluate("postMessage({type: 'party-events:open-tab', tab: 'stats'}, location.origin)")
    expect(page.locator("#appTitle")).to_have_text("Mes stats de jeu")
    page.locator('[data-stats-tab="brain"]').click()
    stats = page.locator("#brainStats")
    expect(stats.locator(".brs-loading")).to_have_count(0, timeout=10000)
    return stats


@pytest.mark.parametrize("width", WIDTHS)
def test_stats_extreme_profile_fits_every_width(make_phone, width):
    """Nombres énormes, palier 20, 200 joueurs aux noms très longs, 365 jours d'historique."""
    phone = make_phone(width=width, height=900)
    me = profile(plays=123456, temperature=2000, history_days=365, level=100, tier=20, best=987654321, index=2000)
    stats = open_stats(phone, me, board(200, name=LONG))
    expect(stats.locator(".brs-board li")).to_have_count(200)
    expect(stats.locator(".brs-game").first).to_contain_text("palier 20")
    no_horizontal_overflow(phone.page, "#brainStats")
    phone.page.wait_for_timeout(2000)
    ratio = phone.page.eval_on_selector(".brs-meter", "m => m.querySelector('i').getBoundingClientRect().width / m.getBoundingClientRect().width")
    assert ratio > 0.97, f"Température 2000 (max) : jauge remplie à {ratio:.0%}"
    phone.shot(f"qa_stats_extreme_{width}")


def test_stats_unbroken_names_do_not_overflow(make_phone):
    phone = make_phone(width=320, height=900)
    stats = open_stats(phone, profile(), board(5, name=UNBROKEN))
    expect(stats.locator(".brs-board li")).to_have_count(5)
    no_horizontal_overflow(phone.page, "#brainStats")


def test_stats_single_game_and_empty_history(make_phone):
    phone = make_phone()
    me = profile(plays=1, history_days=1, level=1, tier=1)
    me["month_progress"] = None
    me["percentile"] = None
    stats = open_stats(phone, me)
    expect(stats).to_contain_text("Ta courbe apparaîtra après quelques jours de jeu")
    expect(stats).to_contain_text("Pas encore un mois de recul")
    expect(stats.locator(".brs-pct")).to_have_count(0)
    expect(stats.locator(".brs-game").filter(has_text="1 partie")).to_have_count(1)


def test_stats_null_fields_do_not_break_the_screen(make_phone):
    phone = make_phone()
    me = {k: None for k in profile()}
    me["games"] = {"pareil": {"index": None, "best": None, "plays": 2, "last_level": None}}
    stats = open_stats(phone, me, {"board": None, "rank": None, "players": None})
    expect(stats.locator(".brs-temp")).to_be_visible()
    expect(stats.locator(".brs-error")).to_have_count(0)


def test_stats_slow_network_shows_loading_then_profile(make_phone):
    phone = make_phone()
    page = phone.page
    pending = []
    page.route("**/api/brain/me", lambda route: pending.append(route))
    page.route("**/api/brain/compare", json_route(board()))
    signed_in(phone)
    page.evaluate("postMessage({type: 'party-events:open-tab', tab: 'stats'}, location.origin)")
    page.locator('[data-stats-tab="brain"]').click()
    expect(page.locator("#brainStats .brs-loading")).to_be_visible()
    expect(page.locator("#brainStats .brs-loading")).to_have_attribute("role", "status")
    page.wait_for_function("() => true")
    page.wait_for_timeout(300)
    pending[0].fulfill(status=200, content_type="application/json", body=json.dumps(profile()))
    expect(page.locator("#brainStats .brs-temp")).to_be_visible()


def test_stats_error_message_is_announced(make_phone):
    phone = make_phone()
    stats = open_stats(phone, {"detail": "Base indisponible"}, status=500)
    expect(stats.locator(".brs-error")).to_have_attribute("role", "alert")
    expect(stats.locator(".brs-error")).to_contain_text("Base indisponible")


def test_stats_trapped_names_are_escaped_everywhere(make_phone):
    phone = make_phone()
    me = profile()
    me["insight"] = TRAP
    me["name"] = TRAP
    stats = open_stats(phone, me, board(3, name=TRAP))
    expect(stats.locator("img")).to_have_count(0)
    phone.page.wait_for_timeout(200)
    assert phone.page.evaluate("window.__pwned") is None


def test_stats_contrast_on_dark_theme_and_reduced_motion(make_phone):
    phone = make_phone(color_scheme="light", reduced_motion="reduce")
    expect(open_stats(phone, profile()).locator(".brs-temp")).to_be_visible()
    page = phone.page
    bad = page.evaluate("""() => {
      const parse = (c) => (c.match(/[\\d.]+/g) || []).slice(0, 4).map(Number);
      const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; };
        return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
      const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor);
        if (c.length >= 3 && (c[3] === undefined || c[3] > .9)) return c; } return parse(getComputedStyle(document.body).backgroundColor); };
      const out = [];
      for (const el of document.querySelectorAll('#brainStats *')) {
        if (!el.childNodes.length || ![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
        const st = getComputedStyle(el);
        if (st.visibility === 'hidden' || st.display === 'none' || el.closest('svg')) continue;
        // Texte en dégradé (background-clip: text) ou posé sur un dégradé : mesuré à part (captures).
        if (st.webkitTextFillColor === 'rgba(0, 0, 0, 0)' || st.backgroundClip === 'text') continue;
        let grad = false; for (let e = el; e && e.id !== 'brainStats'; e = e.parentElement) if (getComputedStyle(e).backgroundImage !== 'none') grad = true;
        if (grad) continue;
        const fg = parse(st.color), bg = bgOf(el);
        const a = fg[3] === undefined ? 1 : fg[3];
        const mix = fg.slice(0, 3).map((v, i) => v * a + bg[i] * (1 - a));
        const [hi, lo] = [lum(mix), lum(bg)].sort((x, y) => y - x);
        const ratio = (hi + .05) / (lo + .05);
        const large = parseFloat(st.fontSize) >= 24 || (parseFloat(st.fontSize) >= 18.66 && +st.fontWeight >= 700);
        if (ratio < (large ? 3 : 4.5)) out.push(`${el.className || el.tagName} « ${el.textContent.trim().slice(0, 30)} » ${ratio.toFixed(2)}`);
      }
      return out;
    }""")
    assert not bad, bad[:10]


def test_stats_on_ipad(make_phone):
    phone = make_phone(device=IPAD)
    stats = open_stats(phone, profile(history_days=365), board(30))
    expect(stats.locator(".brs-board li")).to_have_count(30)
    no_horizontal_overflow(phone.page, "#brainStats")
    phone.shot("qa_stats_ipad")


def test_stats_voiceover_labels(make_phone):
    phone = make_phone()
    stats = open_stats(phone, profile())
    radar = stats.locator(".brs-radar").get_attribute("aria-label")
    assert "Vitesse" in radar and "°M" in radar, radar
    chart = stats.locator(".brs-chart").get_attribute("aria-label")
    assert chart.startswith("Évolution de ta Température"), chart
    expect(stats.locator('[data-stats-tab="brain"]')).to_have_count(0)
    expect(phone.page.locator('[data-stats-tab="brain"]')).to_have_attribute("role", "tab")


# ── Bugs de stats.js trouvés par le testeur des stats, corrigés ensuite ──

def test_stats_ties_share_the_same_rank(make_phone):
    phone = make_phone()
    tied = {"board": [{"id": "a", "name": "Léa", "temperature": 1500, "me": False},
                      {"id": "b", "name": "Tom", "temperature": 1500, "me": True},
                      {"id": "c", "name": "Zoé", "temperature": 900, "me": False}], "rank": 1, "players": 3, "percentile": 50}
    stats = open_stats(phone, profile(), tied)
    expect(stats.locator(".brs-board li .brs-rk")).to_have_text(["1", "1", "3"], timeout=2000)


def test_stats_unreadable_day_never_shows_invalid_date(make_phone):
    phone = make_phone()
    me = profile()
    me["history"] = [{"day": "n'importe quoi", "temperature": 900}] + me["history"]
    stats = open_stats(phone, me)
    expect(stats.locator(".brs-chart")).to_be_visible()
    assert "Invalid" not in (stats.locator(".brs-chart").get_attribute("aria-label") + (stats.locator(".brs-chart").text_content() or ""))


def test_card_gives_focus_back_to_the_player_name_when_closed(make_phone):
    """Clavier / VoiceOver : la fiche fermée, le focus revient sur le nom touché (pas en haut de la page)."""
    phone = make_phone()
    page = phone.page
    page.route("**/api/account/card", json_route(CARD))
    page.route("**/api/brain/compare", json_route({"target": target()}))
    signed_in(phone)
    page.wait_for_timeout(800)  # index.html pose le focus sur le code de la soirée au démarrage (show("pin"), noté)
    page.evaluate("""() => { const b = document.createElement('button'); b.id = 'qaName'; b.textContent = 'Bob';
      b.dataset.profilePid = 'p-bob'; b.dataset.profileGame = '1234'; document.body.append(b); b.focus(); }""")
    page.keyboard.press("Enter")
    expect(page.locator(".pc-card .pc-brain")).to_be_visible()
    expect(page.locator(".pc-close")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".pc-backdrop")).to_have_count(0)
    expect(page.locator("#qaName")).to_be_focused()


def test_card_on_android_by_touch(make_phone):
    """Android (Chrome, tactile) : toucher le nom d'un joueur ouvre la fiche avec Méninges ; toucher le fond la ferme."""
    from tests.e2e.helpers import DEVICES
    phone = make_phone(device=DEVICES["android"])
    page = phone.page
    page.route("**/api/account/card", json_route(CARD))
    page.route("**/api/brain/compare", json_route({"target": target(name=LONG)}))
    signed_in(phone)
    page.evaluate("""() => { const b = document.createElement('span'); b.id = 'qaName'; b.textContent = 'Bob';
      b.dataset.profilePid = 'p-bob'; b.dataset.profileGame = '1234'; b.style.cssText = 'position:fixed;top:200px;left:20px;z-index:50;padding:12px';
      document.body.append(b); }""")
    page.locator("#qaName").tap()
    expect(page.locator(".pc-card .pc-brain-row")).to_have_count(7)
    no_horizontal_overflow(page, ".pc-card")
    page.mouse.click(5, 5)
    expect(page.locator(".pc-backdrop")).to_have_count(0)
