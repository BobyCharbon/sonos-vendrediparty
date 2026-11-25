"""Couverture d'un événement changée après coup (25.11) : base, Pexels, Openverse et Claude simulés.
Droits (comme « Modifier »), CGU, photo réencodée sans GPS, photos proposées sans boisson et choisies par leur numéro
seulement, repli Openverse sans clé, image officielle (jamais un réseau social), limites de recherche, crédits."""
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from app import event_covers as ec
from app.accounts import AccountError, TermsRequired
from app.assistant import ConsentRequired
from app.covers import Covers

EID = "11111111-1111-1111-1111-111111111111"
EVENT = {"id": EID, "title": "Concert de Stephan Eicher", "description": "Au Romandie", "location_name": "Le Romandie",
         "status": "published", "created_by": "org", "cover_url": None, "category": {"name": "Concert"},
         "event_organizers": [{"user_id": "coorg"}], "starts_at": "2026-12-05T20:00:00+00:00", "ends_at": None}


def jpeg(w=800, h=450, gps=False) -> bytes:
    out = io.BytesIO()
    img = Image.new("RGB", (w, h), (200, 40, 120))
    exif = Image.Exif()
    if gps:
        exif[0x8825] = {2: (46.0, 31.0, 0.0), 1: "N"}
    img.save(out, "JPEG", exif=exif.tobytes() if gps else b"")
    return out.getvalue()


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class Accounts:
    def __init__(self, perms=(), terms=(False, True), event=EVENT):
        self.perms, self.terms, self.event, self.calls = set(perms), terms, dict(event), []

    def _uid(self, token):
        return token

    def _perms(self, token):
        return self.perms

    def _get(self, method, path, token, json=None, headers=None):
        self.calls.append((method, path, json))
        if method == "GET":
            return Resp(200, [self.event])
        if path.endswith("/rpc/my_terms"):
            return Resp(200, {"enforced": self.terms[0], "accepted": self.terms[1]})
        if method == "PATCH":
            return Resp(200, [{**self.event, **json, "status": "published"}])
        raise AssertionError(path)


class Claude:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        answer = self.answers.pop(0)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn", usage=None)


class AI:
    def __init__(self, client=None, refuse=None):
        self.client, self.refuse, self.logged = client, refuse, []

    def _check(self, token):
        if self.refuse:
            raise self.refuse
        return token

    def _client_or_error(self):
        return self.client

    def _log(self, *a, **kw):
        self.logged.append(a)

    @staticmethod
    def warn(what, error):
        raise error  # un test ne doit jamais avaler une erreur


class Http:
    def __init__(self, pexels=(), openverse=()):
        self.pexels, self.openverse, self.calls = list(pexels), list(openverse), []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params, headers))
        if "pexels" in url:
            return Resp(200, {"photos": self.pexels})
        return Resp(200, {"results": self.openverse})


def pexel(i, alt="Concert crowd under stage lights"):
    return {"id": i, "alt": alt, "url": f"https://www.pexels.com/photo/{i}/", "photographer": f"Ana {i}",
            "src": {"medium": f"https://images.pexels.com/{i}/m.jpg", "large2x": f"https://images.pexels.com/{i}/l.jpg"}}


def make(tmp_path, ai=None, http=None, key="clé-pexels", perms=(), terms=(False, True), page=None, event=EVENT):
    fetched = []

    def fetch(url):
        fetched.append(url)
        return jpeg(gps=True)
    accounts = Accounts(perms, terms, event)
    covers = Covers(tmp_path, "https://party.test")
    c = ec.EventCovers(accounts, ai or AI(refuse=AccountError("off")), covers, key, http=http or Http(),
                       fetch_image=fetch, read_page=page or (lambda url: {"url": url, "title": "", "description": "", "image": "", "events": []}))
    return c, accounts, fetched


def patch_of(accounts):
    return next(body for m, p, body in accounts.calls if m == "PATCH")


def test_only_the_organization_changes_the_cover(tmp_path):
    c, _, _ = make(tmp_path)
    with pytest.raises(AccountError, match="organisation"):
        c.upload("quelquun", EID, jpeg())
    for who, perms in (("org", ()), ("coorg", ()), ("admin", ("events.manage_all",)), ("modo", ("events.edit_others",))):
        c, accounts, _ = make(tmp_path, perms=perms)
        assert c.upload(who, EID, jpeg())["cover_url"].startswith("https://party.test/covers/")
    draft = {**EVENT, "status": "draft"}
    c, _, _ = make(tmp_path, perms=("events.edit_others",), event=draft)
    with pytest.raises(AccountError):
        c.upload("modo", EID, jpeg())  # le brouillon d'un autre : jamais


def test_my_photo_is_reencoded_without_gps_and_needs_the_terms(tmp_path):
    c, accounts, _ = make(tmp_path)
    saved = c.upload("org", EID, jpeg(1600, 900, gps=True))
    body = patch_of(accounts)
    assert body["cover_url"] == saved["cover_url"] and body["cover_credit"] is None and body["cover_credit_url"] is None
    stored = tmp_path / "covers" / saved["cover_url"].rsplit("/", 1)[1]
    with Image.open(stored) as img:
        assert 0x8825 not in img.getexif()  # GPS retiré
    c, accounts, _ = make(tmp_path, terms=(True, False))
    with pytest.raises(TermsRequired):
        c.upload("org", EID, jpeg())
    assert not [x for x in accounts.calls if x[0] == "PATCH"]
    with pytest.raises(AccountError, match="lue"):
        make(tmp_path)[0].upload("org", EID, b"pas une image")


def test_suggestions_come_from_claude_without_any_drink_and_are_chosen_by_number_only(tmp_path):
    claude = Claude([{"queries": ["concert stage lights", "beer festival", "crowd hands up"]}, {"keep": [2, 1]}])
    http = Http(pexels=[pexel(1), pexel(2, "Friends toasting with beer glasses"), pexel(3, "Crowd at a festival")])
    c, accounts, fetched = make(tmp_path, ai=AI(claude), http=http)
    out = c.suggest("org", EID)
    queries = [p["query"] for _, p, _ in http.calls]
    assert "beer festival" not in queries and queries[0] == "concert stage lights"
    assert http.calls[0][2] == {"Authorization": "clé-pexels"} and http.calls[0][1]["orientation"] == "landscape"
    assert out["ai"] and out["source"] == "pexels"
    # Pexels 2 (bière) écartée par son texte ; Claude a rangé les deux autres (vignette 2 = Pexels 3, puis Pexels 1).
    assert [p["credit"] for p in out["photos"]] == ["Photo : Ana 3 / Pexels", "Photo : Ana 1 / Pexels"]
    assert all(p["thumb"].startswith("data:image/jpeg;base64,") for p in out["photos"])
    assert "https://" not in json.dumps(out)  # aucune adresse d'image externe vers le téléphone
    assert "boisson" in claude.calls[1]["system"] and claude.calls[1]["messages"][0]["content"][1]["type"] == "image"
    assert "Stephan Eicher" in claude.calls[0]["messages"][0]["content"]
    with pytest.raises(AccountError, match="expiré"):
        c.choose("coorg", EID, out["photos"][0]["pick"])  # la proposition d'un autre
    with pytest.raises(AccountError, match="expiré"):
        c.choose("org", EID, "inventé-par-l-app")
    saved = c.choose("org", EID, out["photos"][0]["pick"])
    assert fetched[-1] == "https://images.pexels.com/3/l.jpg"
    body = patch_of(accounts)
    assert body["cover_credit"] == "Photo : Ana 3 / Pexels" and body["cover_credit_url"] == "https://www.pexels.com/photo/3/"
    assert saved["cover_url"].startswith("https://party.test/covers/")


def test_without_a_pexels_key_openverse_is_used_with_free_licences_and_known_words_only(tmp_path):
    http = Http(openverse=[{"id": "ov1", "title": "Concert", "url": "https://live.staticflickr.com/1.jpg",
                            "thumbnail": "https://api.openverse.org/v1/images/ov1/thumb/", "creator": "Jo", "license": "by",
                            "license_version": "4.0", "foreign_landing_url": "https://www.flickr.com/photos/jo/1"},
                           {"id": "ov2", "title": "Wine tasting", "url": "https://x.org/2.jpg",
                            "thumbnail": "https://api.openverse.org/v1/images/ov2/thumb/", "license": "cc0"}])
    c, _, _ = make(tmp_path, ai=AI(refuse=ConsentRequired("Accord requis")), http=http, key="")
    out = c.suggest("org", EID)
    url, params, _ = http.calls[0]
    assert url.startswith("https://api.openverse.org/") and params["license"] == "cc0,pdm,by" and params["mature"] == "false"
    assert params["q"] == "live concert stage lights"  # mot connu, jamais le titre (un prénom peut s'y trouver)
    assert not any("Eicher" in p["q"] for _, p, _ in http.calls)
    assert out["ai"] is False and out["ai_note"] == "consent" and out["source"] == "openverse"
    assert [p["credit"] for p in out["photos"]] == ["Photo : Jo · CC BY 4.0 · Openverse"]


def test_searches_are_limited_per_person(tmp_path):
    c, _, _ = make(tmp_path)
    for _ in range(ec.PER_MINUTE):
        c.suggest("org", EID)
    with pytest.raises(AccountError, match="minute"):
        c.suggest("org", EID)
    c.suggest("coorg", EID)  # une autre personne n'est pas bloquée


def test_the_official_image_comes_from_the_official_page_only(tmp_path):
    def page(url):
        return {"url": url, "title": "Stephan Eicher – Le Romandie", "description": "", "image": "https://leromandie.ch/eicher.jpg", "events": []}
    claude = Claude(['Voici : {"url": "https://www.leromandie.ch/agenda/eicher", "why": "page de la salle"}'])
    c, accounts, fetched = make(tmp_path, ai=AI(claude), page=page)
    out = c.official("org", EID)
    assert out["found"] and out["domain"] == "leromandie.ch" and out["thumb"].startswith("data:image/jpeg")
    assert claude.calls[0]["tools"][0]["type"] == "web_search_20260209"
    c.choose("org", EID, out["pick"])
    assert fetched[-1] == "https://leromandie.ch/eicher.jpg"
    body = patch_of(accounts)
    assert body["cover_credit"] == "Visuel : leromandie.ch" and body["cover_credit_url"] == "https://www.leromandie.ch/agenda/eicher"

    for answer in ('{"url": "https://www.instagram.com/p/xyz", "why": "post"}', '{"url": "", "why": "privé"}', "rien trouvé"):
        c, _, _ = make(tmp_path, ai=AI(Claude([answer])), page=page)
        assert c.official("org", EID) == {"found": False, "message": "Aucune page officielle trouvée pour cet événement."}


def test_the_official_search_needs_the_ai_and_hides_drinks_in_the_app_store_app(tmp_path):
    c, _, _ = make(tmp_path, ai=AI(refuse=ConsentRequired("Accord requis")))
    with pytest.raises(ConsentRequired):
        c.official("org", EID)
    beer = {**EVENT, "title": "Oktoberfest de Lausanne"}
    c, _, _ = make(tmp_path, ai=AI(Claude([])), event=beer)
    assert c.official("org", EID, store=True)["found"] is False


def test_poster_and_removal(tmp_path):
    c, accounts, _ = make(tmp_path)
    saved = c.poster("org", EID)
    assert Covers.is_poster(saved["cover_url"]) and patch_of(accounts)["cover_credit"] is None
    c, accounts, _ = make(tmp_path)
    c.remove("org", EID)
    assert patch_of(accounts) == {"cover_url": None, "cover_credit": None, "cover_credit_url": None}


def test_the_routes_are_account_routes():
    from app.main import app
    paths = {getattr(r, "path", "") for r in app.routes}
    for name in ("photo", "suggest", "official", "choose", "poster", "remove"):
        assert f"/api/account/event-cover/{name}" in paths


def test_the_migration_is_additive_and_replayable():
    sql = open("supabase/migrations/20261125120000_couverture_credit.sql").read()
    assert "add column if not exists cover_credit text" in sql and "drop constraint if exists events_cover_credit_check" in sql
    assert "drop table" not in sql.lower() and "drop column" not in sql.lower()
