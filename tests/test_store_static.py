"""App App Store (« PartyStore ») après le contrôle du 26.11 :
- la page et TOUS les scripts et styles qu'elle charge (chargements différés compris) ne contiennent ni le code des jeux
  cachés ni un mot de boisson, de gorgée, de shot, de bière, de casino ou de drogue (app/store_static.py) ; le web et la
  BETA reçoivent /static/ tel quel ;
- les jeux : aucun texte lu par la table (prénom, réponse, mot, prénom ajouté) sans la case des conditions (Apple 1.2,
  main.py check_game_terms) ; le mot proposé par le Fantôme de L'Intrus n'est jamais envoyé à la table."""
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import games, main, store_static

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
BETA_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0"
WEB_UA = "Mozilla/5.0 Safari"
ASSET = re.compile(r"""(/static(?:-store)?/[\w./-]+\.(?:js|css))(?=["'`?])""")


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


def client(ua):
    return TestClient(main.app, headers={"User-Agent": ua})


def served(ua) -> dict[str, str]:
    """La page et tout ce qu'elle charge, de proche en proche (scripts chargés plus tard compris)."""
    c = client(ua)
    html = c.get("/").text
    out, todo = {"/": html}, set(ASSET.findall(html))
    while todo:
        path = todo.pop()
        if path in out:
            continue
        r = c.get(path)
        assert r.status_code == 200, path
        out[path] = r.text
        if path.endswith(".js"):
            todo |= set(ASSET.findall(r.text)) - set(out)
    return out


def test_the_store_app_page_and_every_script_it_loads_have_no_drink_word():
    files = served(STORE_UA)
    assert len(files) > 30
    assert all(p.startswith("/static-store/") for p in files if p != "/"), [p for p in files if p.startswith("/static/")]
    found = {p: sorted({m.group(0).lower() for m in store_static.CODE_DRINK_RE.finditer(t)}) for p, t in files.items()}
    assert {p: w for p, w in found.items() if w} == {}
    # Le code des jeux cachés n'est pas servi : ni leurs fichiers, ni leurs règles, ni leur table de points.
    page = files["/"]
    for name in ("purity.js", "beerpong.js", "purity.css", "beerpong.css"):
        assert f"/{name}" not in page
    js = files[next(p for p in files if p.endswith("/games.js"))]
    for code in ("CANDY_SWAPS = [\n", "BJ_RULES", "CASINO_RULES", "renderCasinoHost", "bjTableHtml", "BK_RULES", "pyrHtml",
                 "neverResultsHtml", "<store-cut", "<store>"):
        assert code not in js, code


@pytest.mark.parametrize("ua", [WEB_UA, BETA_UA])
def test_the_web_and_the_beta_keep_every_game(ua):
    c = client(ua)
    page = c.get("/").text
    assert "/static/games.js" in page and "/static/purity.js" in page and "/static-store/" not in page
    js = c.get("/static/games.js").text
    assert "gorgée" in js and "renderCasinoHost" in js and "<store-cut>" in js


@pytest.mark.skipif(not shutil.which("node"), reason="node absent")
def test_every_store_script_still_parses(tmp_path):
    for path, text in served(STORE_UA).items():
        if not path.endswith(".js") or "import(" in text or re.search(r"^\s*(?:import|export)\b", text, re.M):
            continue
        f = tmp_path / path.strip("/").replace("/", "_")
        f.write_text(text, encoding="utf-8")
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, (path, r.stderr[:500])


def test_store_static_serves_only_static_files():
    c = client(STORE_UA)
    assert c.get("/static-store/../main.py").status_code == 404
    assert c.get("/static-store/%2e%2e/main.py").status_code == 404
    assert c.get("/static-store/nope.js").status_code == 404
    assert c.get("/static-store/icon-192.png").status_code == 200


def test_markers_cut_lines_blocks_and_keep_the_store_lines():
    src = ("const a = 1; // <store-cut/>\n// <store> const a = 2;\n// <store-cut> x\nconst gone = 'bière';\n// </store-cut>\n"
           "const t = `<p>web</p> <!-- store-cut -->\n<!-- <store> <p>app</p> -->\n`;\nconst u = 'a // b'; // fin\n")
    out = store_static.js(src)
    assert "const a = 2;" in out and "const a = 1" not in out and "bière" not in out
    assert "<p>app</p>" in out and "<p>web</p>" not in out and "const u = 'a // b';" in out and "fin" not in out


# ── Conditions d'utilisation des jeux (Apple 1.2) ──
def create(ua, gid, kind="tmc", **extra):
    main._game_creations.clear()
    return client(ua).post("/api/games", json={"guest_id": gid, "name": "Léa", "type": kind, **extra})


def act(ua, code, gid, action, **extra):
    return client(ua).post(f"/api/games/{code}", json={"guest_id": gid, "name": gid[:10], "action": action, **extra})


def test_the_store_app_asks_for_the_terms_before_any_text_the_table_reads():
    r = create(STORE_UA, "store-terms-host")
    assert r.status_code == 403 and r.json()["code"] == "games_terms" and "conditions" in r.json()["detail"]
    code = create(STORE_UA, "store-terms-host", terms=True).json()["code"]
    g = main.store.session.games[code]
    assert games.player(g, "store-terms-host")["terms"]
    # Rejoindre (son prénom est lu par la table) : la case d'abord ; ensuite, plus besoin de la renvoyer.
    assert act(STORE_UA, code, "store-terms-bob1", "join").json()["code"] == "games_terms"
    assert act(STORE_UA, code, "store-terms-bob1", "join", terms=True).status_code == 200
    assert games.player(g, "store-terms-bob1")["terms"]
    assert act(STORE_UA, code, "store-terms-host", "addguest", guess="Max").status_code == 200
    # Une place prise sans la case (le web, une ancienne version) : l'app refuse son texte jusqu'à la case.
    assert act(WEB_UA, code, "web-terms-cleo", "join").status_code == 200
    assert act(STORE_UA, code, "web-terms-cleo", "addguest", guess="Zoé").status_code == 403  # animateur seul, de toute façon
    r = act(STORE_UA, code, "web-terms-cleo", "tanswer", guess="Ma réponse")
    assert r.status_code == 403 and r.json()["code"] == "games_terms"
    # Les actions sans texte restent ouvertes (voter, partir…).
    assert act(STORE_UA, code, "web-terms-cleo", "leave").status_code == 200


def test_the_web_and_the_beta_need_no_box_but_a_party_account_in_the_app_does():
    for i, ua in enumerate((WEB_UA, BETA_UA)):
        code = create(ua, f"web-noterms-{i}").json()["code"]
        assert act(ua, code, f"web-noterms-b{i}", "join").status_code == 200
    # Contrôle du 26.11 (tour 1) : plus de dispense « acct- » dans l'app App Store, la case une fois par appareil.
    r = create(STORE_UA, "acct-0123456789abcdef")
    assert r.status_code == 403 and r.json()["code"] == "games_terms"
    assert create(STORE_UA, "acct-0123456789abcdef", terms=True).status_code == 200


def test_the_store_page_has_no_account_dispensation_for_the_box():
    files = served(STORE_UA)
    games_js = files[next(p for p in files if p.endswith("/games.js"))]
    assert "acct-" not in games_js.split("function gamesTermsOk")[1].split("}")[0]


def test_hidden_game_words_never_reach_the_store_app():
    """Code dormant des jeux cachés (Roulette, Casino, Blackjack, Je n'ai jamais…) et mots de jeu d'argent : coupés."""
    words = re.compile(r"jetons?|jackpot|je n['’]ai jamais|roulette|casino|blackjack|trou du cul|\bpari", re.I)
    found = {p: sorted({m.group(0).lower() for m in words.finditer(t)}) for p, t in served(STORE_UA).items()}
    assert {p: w for p, w in found.items() if w} == {}


def test_no_comment_in_the_inline_scripts_of_the_store_page():
    page = served(STORE_UA)["/"]
    for script in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page, re.S):
        assert not re.search(r"^\s*//", script, re.M), script[:200]
    assert "Android plus tard" not in page


@pytest.mark.parametrize("path", ["pet/zicou-home.js", "purity.js", "beerpong.js", "purity.css", "beerpong.css",
                                  "brain/../purity.js"])
def test_hidden_game_files_are_404_for_the_store_app(path):
    c = client(STORE_UA)
    assert c.get(f"/static-store/{path}").status_code == 404
    assert c.get(f"/static/{path}").status_code == 404
    if "pet/" not in path and ".." not in path:  # Zicou : son propre drapeau (compagnon_enabled) côté site
        assert client(WEB_UA).get(f"/static/{path}").status_code == 200


# ── Prénoms (contrôle du 26.11, tour 1) ──
def test_a_renamed_player_goes_through_the_same_filter_and_box_as_the_entry():
    code = create(STORE_UA, "store-name-host", terms=True).json()["code"]
    g = main.store.session.games[code]
    c = client(STORE_UA)
    for bad in ("connard", "Vodka Max", "Léa shot", "Hitler", "Ganja", "Putain"):
        c.get(f"/api/games/{code}", params={"guest_id": "store-name-host", "name": bad})
        assert games.player(g, "store-name-host")["name"] == "Léa"
        c.post(f"/api/games/{code}", json={"guest_id": "store-name-host", "name": bad, "action": "pause"})
        assert games.player(g, "store-name-host")["name"] == "Léa"
        assert c.post("/api/presence", json={"guest_id": "store-name-host", "name": bad}).status_code == 400
    c.get(f"/api/games/{code}", params={"guest_id": "store-name-host", "name": "Lucie"})
    assert games.player(g, "store-name-host")["name"] == "Lucie" and g["host_name"] == "Lucie"
    # Place prise sans la case (le web) : l'app ne la renomme pas avant la case.
    assert act(WEB_UA, code, "web-name-cleo1", "join").status_code == 200
    c.get(f"/api/games/{code}", params={"guest_id": "web-name-cleo1", "name": "Cléo"})
    assert games.player(g, "web-name-cleo1")["name"] == "web-name-c"
    # Le web garde le filtre commun (insultes), sans le filtre de boisson de l'app.
    web = client(WEB_UA)
    assert web.post("/api/presence", json={"guest_id": "web-name-cleo1", "name": "connard"}).status_code == 400
    assert web.post("/api/presence", json={"guest_id": "web-name-cleo1", "name": "Vodka"}).status_code == 200
    assert web.post("/api/presence", json={"guest_id": "web-name-cleo1", "name": "Merde"}).status_code == 200  # tour 3 : app seule


def test_the_store_view_shows_joueur_for_a_drink_or_insult_name_and_no_sips():
    code = create(WEB_UA, "web-view-host1").json()["code"]
    g = main.store.session.games[code]
    games.player(g, "web-view-host1")["name"] = g["host_name"] = "Vodka Max"  # prénom d'avant le filtre, ou du web
    g["players"].append({**games.player(g, "web-view-host1"), "id": "web-view-bob01", "pid": "bobpid", "name": "connard"})
    g["host"] = "nobody"
    view = client(STORE_UA).get(f"/api/games/{code}", params={"guest_id": "web-view-bob01"}).json()
    # Contrôle Apple, tour 4 : réécrits DANS la partie, chacun son numéro (store_app.scrub_names).
    assert [p["name"] for p in view["players"]] == ["Joueur 1", "Joueur 2"] and view["host_name"].startswith("Joueur ")
    text = str(view)
    assert "Vodka" not in text and "connard" not in text
    assert "'drink'" not in text and "'give'" not in text and "sips_log" not in view
    web = client(WEB_UA).get(f"/api/games/{code}", params={"guest_id": "web-view-bob01"}).json()
    assert web["players"][0]["name"] == "Joueur 1" and "drink" in web["players"][0]  # partie touchée par l'app


def test_the_quiz_leaderboard_hides_drink_and_insult_names_in_the_store_app(monkeypatch):
    from app import quiz
    stats = {"players": {"a": {"name": "Bière Bob", "pts": 9, "games": 1, "wins": 1, "ok": 1, "n": 1, "best_streak": 1,
                               "records": {"classic": 9}},
                         "b": {"name": "Zoé", "pts": 5, "games": 1, "wins": 0, "ok": 1, "n": 1, "best_streak": 1},
                         "c": {"name": "connard", "pts": 1, "games": 1, "wins": 0, "ok": 1, "n": 1, "best_streak": 1}}}
    monkeypatch.setattr(quiz, "_load_stats", lambda: stats)
    store = quiz.leaderboard(store=True)
    assert [x["name"] for x in store["top"]] == ["Joueur 1", "Zoé", "Joueur 2"]  # distincts (contrôle Apple, tour 4)
    assert all(r["name"] == "Joueur 1" for r in store["records"].values())
    assert quiz.leaderboard()["top"][0]["name"] == "Bière Bob"


def test_the_ghost_word_is_never_sent_to_the_table():
    code = create(WEB_UA, "ghost-host-01", kind="undercover", white=True).json()["code"]
    g = main.store.session.games[code]
    for i in range(4):
        games.join(g, f"ghost-p{i}-000", f"P{i}")
    games.start(g)
    white = next(p["id"] for p in g["players"] if p["role"] == "white")
    games.start_vote(g)
    games.eliminate(g, white)
    games.white_guess(g, white, "Pastèque")
    view = client(WEB_UA).get(f"/api/games/{code}?guest_id=ghost-p0-000").json()
    assert view["last"]["guess"] is True and "Pastèque" not in str(view)


# ── Contrôle du 26.11, tour 2 ──
def raw_get(path, ua=STORE_UA):
    """Comme `curl --path-as-is` : le chemin arrive au serveur tel quel, `..` et `%2e` compris."""
    import asyncio
    import httpx

    async def get():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://t",
                                     headers={"User-Agent": ua}) as c:
            req = c.build_request("GET", "http://t/")
            req.url = req.url.copy_with(raw_path=path.encode())
            return await c.send(req)
    # Fil à part : un test de navigateur lancé plus tôt (Playwright) peut laisser une boucle asyncio sur ce fil.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, get()).result()


@pytest.mark.parametrize("path", ["/static/%2e%2e/static/purity.js", "/static/../static/purity.js", "/static/./purity.js",
                                  "/static/brain/../purity.js", "/static/%2E%2E/static/beerpong.css",
                                  "/static-store/%2e%2e/static/purity.js", "/static-store/./purity.js",
                                  "/static-store/brain/%2e%2e/purity.js"])
def test_dot_segments_never_reach_a_hidden_game_file(path):
    r = raw_get(path)
    assert r.status_code == 404, (path, r.status_code)
    assert "purity" not in r.text.lower()


def test_the_store_app_gets_no_script_or_style_by_static():
    c = client(STORE_UA)
    for path in ("/static/games.js", "/static/style.css", "/static/likely.js", "/static/nav.js"):
        assert c.get(path).status_code == 404, path
    assert c.get("/static/icon-192.png").status_code == 200
    web = client(WEB_UA)
    assert web.get("/static/games.js").status_code == 200 and web.get("/static/style.css").status_code == 200
    assert raw_get("/static/purity.js", WEB_UA).status_code == 200


def test_no_dormant_hidden_game_or_zicou_text_in_the_store_app():
    files = served(STORE_UA)
    js = files[next(p for p in files if p.endswith("/games.js"))]
    admin = files[next(p for p in files if p.endswith("/games-admin.js"))]
    page = files["/"]
    words = re.compile(r"pyramide|lancer la pyramide|\bmises?\b|purify|pyjama|zicou|gorgée|PYR_Q|pyrLook|questionHtml|"
                       r"neverResults|\bsips\s*=|tallyTxt = \(p\)|whoof: \"", re.I)
    for name, text in (("games.js", js), ("games-admin.js", admin), ("index", page)):
        assert not words.findall(text), (name, sorted({w.lower() for w in words.findall(text)}))
    assert "<!--" not in re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", page, flags=re.S)
    assert "purityStats" not in page and "Android" not in page
    # Le web garde tout.
    web = client(WEB_UA)
    wjs = web.get("/static/games.js").text
    assert "Lancer la pyramide" in wjs and "pyjama" in wjs and 'bet: "Mises"' in wjs and "data-pet-name" in wjs
    assert "purityStats" in web.get("/").text


def test_the_store_app_refuses_a_drink_name_when_creating_a_game():
    r = create(STORE_UA, "store-create-name", terms=True, name="Vodka Max")
    assert r.status_code == 400
    assert create(WEB_UA, "web-create-name1", name="Vodka Max").status_code == 200


def test_round_three_no_dormant_sips_buttons_friends_pack_or_hidden_game_list_in_the_store_app():
    """Contrôle Apple tour 3 : le code éteint n'est pas servi (boutons de gorgées de Qui est le plus…, paquet
    « Entre amis », liste des jeux cachés) ; le web le garde."""
    files = served(STORE_UA)
    js = files[next(p for p in files if p.endswith("/games.js"))]
    lk = files[next(p for p in files if p.endswith("/likely.js"))]
    for word in ("data-lk-sips", "stakes", "Entre amis", "lkSips"):
        assert word not in lk, word
    assert "Entre amis" not in js and 'data-opt="lkfriends"' not in js
    assert "const STORE_HIDDEN = [];" in js
    for game in ("beerpong", "biskit", "purity", "pyramid", "whoof", '"never"', "roulette", "casino", "blackjack"):
        assert game not in js, game
    web = client(WEB_UA)
    wlk, wjs = web.get("/static/likely.js").text, web.get("/static/games.js").text
    assert "data-lk-sips" in wlk and "Entre amis" in wlk and 'data-opt="lkfriends"' in wjs
    assert 'STORE_HIDDEN = STORE ? ["casino"' in wjs
