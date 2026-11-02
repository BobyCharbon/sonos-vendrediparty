"""Lire un lien d'événement pour l'IA : infos de la page (titre, schema.org, billets, texte), adresses internes refusées,
redirection vers le réseau local refusée, image de couverture en https seulement, et passage des sources à Claude."""
import json

import httpx
import pytest

from app import ai_events as ev
from app import link_reader as lr
from tests.test_ai_events import READY, make

PAGE = """<html><head><title>Fallback</title>
<meta property="og:title" content="TECHNOABTEIL Swiss Tour &#8211; Bern">
<meta property="og:description" content="20. November 2026 22:00 – 06:00">
<meta property="og:image" content="https://cdn.example.ch/flyer.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"MusicEvent","name":"Swiss Tour",
 "startDate":"2026-11-20T22:00","location":{"@type":"Place","name":"Bierhübeli","address":"Neubrückstrasse 43, 3012 Bern"}}</script>
<style>.x{}</style><script>var secret = 1;</script></head>
<body><h1>Swiss Tour</h1><p>19 ARTISTS. 2 FLOORS.</p><a href="https://shop.bookinea.app/en">Get Ticket</a></body></html>"""


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    lr._cache.clear()
    monkeypatch.setattr(lr, "_public", lambda host: host not in ("localhost", "intranet.local"))


def client(pages):
    def handler(request):
        page = pages.get(str(request.url))
        if isinstance(page, tuple):
            return httpx.Response(302, headers={"location": page[1]})
        return httpx.Response(200, html=page) if page else httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_page_gives_its_title_structured_event_tickets_and_text():
    info = lr.read("https://technoabteil.ch/e", client({"https://technoabteil.ch/e": PAGE}))
    assert info["title"] == "TECHNOABTEIL Swiss Tour – Bern"
    assert info["events"][0]["location"]["name"] == "Bierhübeli"
    assert info["tickets"] == ["https://shop.bookinea.app/en"]
    assert "19 ARTISTS" in info["text"] and "secret" not in info["text"]  # ni script ni style
    assert lr.cover([info]) == "https://cdn.example.ch/flyer.jpg"
    block = lr.as_prompt("https://technoabteil.ch/e", info)
    assert block.startswith('<page url="https://technoabteil.ch/e">') and block.endswith("</page>")


def test_internal_addresses_and_redirects_to_them_are_refused():
    with pytest.raises(lr.LinkError, match="non publique"):
        lr.read("http://localhost:8000/admin", client({}))
    with pytest.raises(lr.LinkError, match="non publique"):
        lr.read("https://bit.ly/x", client({"https://bit.ly/x": ("redirect", "http://intranet.local/")}))
    with pytest.raises(lr.LinkError):
        lr.read("file:///etc/passwd", client({}))
    with pytest.raises(lr.LinkError, match="404"):
        lr.read("https://example.ch/none", client({}))


def test_urls_are_found_in_what_was_said_without_trailing_punctuation():
    said = "Regarde https://a.ch/event/1. Et aussi (https://b.ch/x), puis https://c.ch/y"
    assert lr.find_urls(said) == ["https://a.ch/event/1", "https://b.ch/x"]  # deux liens au plus


def test_the_ai_receives_the_page_and_screenshots_and_the_cover_is_kept(tmp_path, monkeypatch):
    info = lr.read("https://technoabteil.ch/e", client({"https://technoabteil.ch/e": PAGE}))
    monkeypatch.setattr(lr, "read", lambda url: info)
    a, accounts, claude = make(tmp_path, READY)
    d = a.draft("ok", ["https://technoabteil.ch/e"], None, images=["data:image/png;base64," + "A" * 400])
    content = claude.calls[0]["messages"][0]["content"]
    kinds = [b["type"] for b in content]
    assert kinds == ["text", "text", "image", "text"]
    assert "Bierhübeli" in content[1]["text"] and content[2]["source"]["media_type"] == "image/png"
    assert "DONNÉES" in claude.calls[0]["system"]  # le contenu des pages n'est jamais une instruction
    assert d["cover_url"] == "https://cdn.example.ch/flyer.jpg"
    a.create("ok", d, {"name": "Bierhübeli", "address": "Neubrückstrasse 43, 3012 Bern"})
    row = next(b for m, p, b in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["cover_url"] == "https://cdn.example.ch/flyer.jpg"


def test_an_unreadable_link_is_told_to_the_ai(tmp_path, monkeypatch):
    def broken(url):
        raise lr.LinkError("la page répond 403")
    monkeypatch.setattr(lr, "read", broken)
    a, _, claude = make(tmp_path, READY)
    a.draft("ok", ["https://instagram.com/p/x"], None)
    assert "illisible (la page répond 403)" in json.dumps(claude.calls[0]["messages"], ensure_ascii=False)
