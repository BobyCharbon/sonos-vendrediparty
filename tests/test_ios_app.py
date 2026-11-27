"""Apps iOS natives (ios/) : fichier des liens universels servi par le site, pour que les QR codes ouvrent l'app.

Le site principal ouvre VendrediParty (ch.bobycharbon.party), le site de test VendrediPartyBETA (….beta)."""
from fastapi.testclient import TestClient

from app import main


def app_ids(monkeypatch, public_url):
    if public_url is None:
        monkeypatch.delenv("PARTY_PUBLIC_URL", raising=False)
    else:
        monkeypatch.setenv("PARTY_PUBLIC_URL", public_url)
    r = TestClient(main.app).get("/.well-known/apple-app-site-association", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    details = r.json()["applinks"]["details"]
    # Admin, Apple TV, API, fichiers, Agenda et Pronos publics restent dans le navigateur (contrôle Apple du 26.11,
    # tours 1 et 2) : exclus avant « tout le reste ».
    excluded = ["/admin*", "/tv*", "/api/*", "/static*", "/d/*", "/agenda/*", "/prono/*"]
    assert [d["components"] for d in details] == [[*({"/": x, "exclude": True} for x in excluded), {"/": "/*"}]]
    return details[0]["appIDs"]


def test_main_site_opens_the_app_store_app(monkeypatch):
    assert app_ids(monkeypatch, None) == ["GS2B6GA9JA.ch.bobycharbon.party"]
    assert app_ids(monkeypatch, "https://party.bobycharbon.ch") == ["GS2B6GA9JA.ch.bobycharbon.party"]


def test_test_site_opens_the_beta_app(monkeypatch):
    assert app_ids(monkeypatch, "https://partytest.bobycharbon.ch/") == ["GS2B6GA9JA.ch.bobycharbon.party.beta"]


# ── Pas de zoom : l'app doit se sentir native, pas comme un site web ──
_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
NO_ZOOM = "maximum-scale=1, user-scalable=no"


def test_every_page_forbids_zooming():
    for page in ("app/static/index.html", "app/static/admin.html", "app/static/tv.html", "web/events/scripts/postbuild.mjs"):
        assert NO_ZOOM in (_ROOT / page).read_text(encoding="utf-8"), page


def test_pinch_and_double_tap_zoom_are_blocked_in_the_page():
    js = (_ROOT / "app/static/ios-app.js").read_text(encoding="utf-8")
    assert '"gesturestart"' in js and "preventDefault" in js
    css = (_ROOT / "app/static/style.css").read_text(encoding="utf-8")
    assert "touch-action: manipulation" in css


def test_native_app_web_view_cannot_zoom():
    swift = (_ROOT / "ios/Party/PartyWebView.swift").read_text(encoding="utf-8")
    assert "maximumZoomScale = 1" in swift and "viewForZooming" in swift


# ── Android (android/) : Digital Asset Links, pour que l'app s'ouvre sans barre d'adresse ──
def asset_links(monkeypatch, public_url):
    monkeypatch.setenv("PARTY_PUBLIC_URL", public_url)
    r = TestClient(main.app).get("/.well-known/assetlinks.json", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    [statement] = r.json()
    assert statement["relation"] == ["delegate_permission/common.handle_all_urls"]
    assert statement["target"]["namespace"] == "android_app"
    assert main.ANDROID_UPLOAD_KEY_SHA256 in statement["target"]["sha256_cert_fingerprints"]
    return statement["target"]["package_name"]


def test_main_site_declares_the_play_store_app(monkeypatch):
    assert asset_links(monkeypatch, "https://party.bobycharbon.ch") == "ch.bobycharbon.party"


def test_test_site_declares_the_android_beta_app(monkeypatch):
    assert asset_links(monkeypatch, "https://partytest.bobycharbon.ch") == "ch.bobycharbon.party.beta"


def test_recette_hooks_never_reach_the_app_store_build():
    """Crochets de la recette réelle (brouillon et session injectés) : compilés en Debug, ou en Release seulement quand la
    recette passe PARTY_SWIFT_CONDITIONS=E2E_HOOKS en ligne de commande ; jamais dans project.yml ni le workflow."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert "E2E_HOOKS" not in (root / "ios/project.yml").read_text(encoding="utf-8")
    for workflow in (root / ".github/workflows").glob("*.yml"):
        assert "E2E_HOOKS" not in workflow.read_text(encoding="utf-8"), workflow.name
    app = (root / "ios/Party/PartyApp.swift").read_text(encoding="utf-8")
    hooks = app.split("#if DEBUG || E2E_HOOKS\n", 1)[1].split("#endif", 1)[0]
    for demo in ("HostDemo", "GroupAdminDemo", "AIEventDemo"):  # écrans figés des tests d'interface en Release
        assert f".overlay {{ {demo}(model: model) }}" in hooks, demo


def test_testflight_builds_the_iphone_app_with_the_ios_27_1_sdk():
    """iPhone Duo (18.11) : compilée avec un SDK plus ancien, l'app y tourne en mode compatibilité (bandes noires, barre
    d'onglets en bas). Le job iPhone tourne sur le Mac de l'admin (runner « party-mac »), Xcode épinglé à 27.1 ou plus ;
    cible iOS 16."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ios-testflight.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  testflight:\n", 1)[1].split("\n  tvos:\n", 1)[0]
    assert "runs-on: [self-hosted, party-mac]" in job
    version = re.search(r'XCODE_VERSION: "(\d+)\.(\d+)"', job)
    assert version and (int(version[1]), int(version[2])) >= (27, 1), "Xcode épinglé à 27.1 ou plus"
    assert 'iOS: "16.0"' in (root / "ios/project.yml").read_text(encoding="utf-8")


def test_review_notes_describe_every_big_feature_delivered_by_the_web():
    """Apple 2.3.1(a) : chaque grosse fonction livrée par le site dans l'app iOS est décrite dans les notes pour les
    examinateurs (ios/appstore/review-notes.txt, envoyées par tools/appstore_submit.py, 4 000 caractères au plus)."""
    from pathlib import Path
    notes = (Path(__file__).resolve().parents[1] / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    assert len(notes) <= 4000
    features = {
        "invitations v2 (liens pour une personne / Plusieurs)": "Plusieurs",
        "partage commun (chaque invité crée ses liens)": "own links",
        "accord de l'organisateur": "À accepter",
        "sondage de dates": "Date poll",
        "agenda abonné": "calendar feed",
        "covoiturage": "Carpool",
        "liens de groupe": '"Inviter" > "Le lien du groupe"',
        "inscription complète des invités": "nickname",
        "nouveau compte": "Nouveau compte",
        "annonce et maintenance": "maintenance",
        "billets QR / Wallet": "Wallet",
        "fiche en direct": "updates live",
        "nom qui ouvre le profil": "open the profile",
        "heure des réponses et des votes": "shows its time",
        "surnom à 12 caractères": "12 characters",
        "refus 1.4.3 : plus de jeu à boire (25.11)": "No drinking games",
        "refus 1.4.3 : ce qui a été retiré": "Changes since the 1.4.3 rejection",
    }
    missing = [name for name, word in features.items() if word.lower() not in notes.lower()]
    assert not missing, missing


def test_workflows_run_on_the_admin_machines_and_testflight_never_on_develop():
    """Dépôt privé (24.11) : tous les jobs sur les runners auto-hébergés (Mac de l'admin pour Apple et Android, serveur
    pour Linux), jamais sur une machine GitHub payante. TestFlight ne part plus à chaque push sur develop."""
    from pathlib import Path
    import re
    root = Path(__file__).resolve().parents[1]
    for workflow in (root / ".github/workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        for runs_on in re.findall(r"runs-on: (.+)", text):
            assert runs_on.strip() in ("[self-hosted, party-mac]", "[self-hosted, party-linux]"), (workflow.name, runs_on)
        assert "maxim-lobanov/setup-xcode" not in text, workflow.name  # demande sudo sur le Mac de l'admin
    testflight = (root / ".github/workflows/ios-testflight.yml").read_text(encoding="utf-8")
    push = testflight.split("  push:\n", 1)[1].split("\n  workflow_dispatch:", 1)[0]
    assert "branches: [main]" in push and "develop" not in push
    assert "envoi:" in testflight and "UPLOAD" in testflight
