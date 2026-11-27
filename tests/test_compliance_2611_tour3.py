"""Contrôle Apple du 26.11, tour 3 (serveur et module web) : police hébergée par le serveur (aucune requête à Google),
politique (web = iPhone) sur l'IA, les moyens de paiement « On me paie » et les durées, fiche qui masque les contenus
d'une personne bloquée, blocage depuis les réglages d'un message direct signalé aux écrans ouverts."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import main

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pages_load_bricolage_from_the_party_server_never_from_google():
    for page in ("app/static/index.html", "app/static/admin.html", "app/static/tv.html"):
        text = read(page)
        assert "fonts.googleapis" not in text and "fonts.gstatic" not in text, page
        assert '<link rel="stylesheet" href="/static/fonts/fonts.css">' in text, page
    css = read("app/static/fonts/fonts.css")
    assert "googleapis" not in css and "gstatic" not in css
    c = TestClient(main.app)
    for name in ("latin-700", "latin-800", "latin-ext-700", "latin-ext-800"):
        assert f"/static/fonts/bricolage-grotesque-{name}-normal.woff2" in css
        r = c.get(f"/static/fonts/bricolage-grotesque-{name}-normal.woff2")
        assert r.status_code == 200 and r.content[:4] == b"wOF2", name
    assert "SIL Open Font License" in read("app/static/fonts/OFL.txt")
    assert "googleapis" not in "".join(read(p) for p in ("web/events/src/app/_layout.tsx", "web/events/src/lib/theme.ts"))


def test_privacy_says_what_the_ai_gets_and_how_long_web_and_iphone_alike():
    for path in ("web/events/src/app/privacy.tsx", "ios/Party/Settings/Account/SignInView.swift"):
        text = read(path).replace("’", "'")
        assert "les personnes déjà choisies, sous un alias ; la liste des membres n'est jamais envoyée" in text, path
        assert "la liste des membres de Party que tu peux inviter" not in text, path
        assert "police de caractères" not in text, path
        assert "chaque appel est effacé au bout de 12 mois" in text and "Journal des appels à l'IA : 12 mois." in text, path
        assert "en « On me paie » (jamais en paiement en ligne ni sur place)" in text, path
    consent = read("web/events/src/lib/aiConsent.ts").replace("’", "'")
    said = "les personnes déjà choisies, sous un alias (P1, P2…), jamais leur nom ; pour modifier un événement avec l'IA, aussi son contenu actuel"
    assert said in consent and "ainsi que ton surnom, les noms de tes groupes" in consent
    assert said in read("app/static/index.html")


def test_on_me_paie_says_the_payment_details_are_shown_to_those_who_come():
    assert "Tes moyens de paiement (Réglages › Pot commun) seront montrés aux personnes qui viennent." in read(
        "web/events/src/components/EventForm.tsx")


def test_blocking_hides_notes_bring_items_and_poll_choices_on_the_event():
    sections = read("web/events/src/components/EventSections.tsx")
    assert sections.count("useBlockedIds()") == 3
    assert "!blocked.has(n.user_id)" in sections and "!blocked.has(o.created_by)" in sections
    assert "!blocked.has(it.added_by)" in sections
    assert "blocksChanged(other.id, next);" in read("web/events/src/components/DirectChatSettings.tsx")
