"""Aperçu des liens d'un événement PUBLIC (campagne 2, rapport 10 n° 5) : /events/event/<id>, /events/share/<id> et le
lien de « Partager le lien » (/?tab=events&event=<id>) montrent titre, date et image dans WhatsApp / iMessage, jamais
l'adresse exacte. Événement non public (public_event ne le rend pas) ou base injoignable : aucun aperçu propre à
l'événement, la page s'ouvre quand même."""
import json

import pytest
from fastapi.testclient import TestClient

from app import event_preview, main
from tests.test_app_invites import fake

EVENT = "33333333-3333-4333-8333-333333333333"
PUBLIC = {"id": EVENT, "title": 'Raclette & "vinyles"<script>x</script>', "status": "published",
          "starts_at": "2026-11-14T20:00:00Z", "all_day": False, "location_name": "Chez Ludo",
          "location_address": "Rue Secrète 12, 1000 Lausanne", "description": "Apporte ton fromage."}


@pytest.fixture
def page_dir(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>Party</title></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path)
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://party.bobycharbon.ch")
    main._pages.clear()
    return tmp_path


def _client(monkeypatch, reply, status=200):
    acc, seen = fake({"public_event": reply}, status=status)
    monkeypatch.setattr(main, "accounts", acc)
    return TestClient(main.app), seen


@pytest.mark.parametrize("path", [f"/events/event/{EVENT}", f"/events/share/{EVENT}", f"/events/share/{EVENT}/",
                                  f"/?tab=events&event={EVENT}"])
def test_public_event_links_have_a_rich_escaped_preview_without_the_address(monkeypatch, page_dir, path):
    client, seen = _client(monkeypatch, PUBLIC)
    page = client.get(path).text
    assert 'property="og:title" content="Raclette &amp; &quot;vinyles&quot;&lt;script&gt;x&lt;/script&gt;"' in page
    assert "<script>x" not in page
    assert "sam. 14 nov. · 21:00 · Chez Ludo" in page
    assert 'property="og:image" content="https://party.bobycharbon.ch/static/icon-512.png"' in page
    assert f'property="og:url" content="https://party.bobycharbon.ch/events/share/{EVENT}"' in page
    assert "Rue Secrète" not in page and "1000 Lausanne" not in page
    assert page.count('property="og:title"') == 1
    rpc = [(p, json.loads(b)) for p, b, _ in seen if p.endswith("/public_event")]
    assert rpc == [("/rest/v1/rpc/public_event", {"e": EVENT})]


@pytest.mark.parametrize("path", [f"/events/event/{EVENT}", f"/events/share/{EVENT}", f"/?tab=events&event={EVENT}"])
def test_a_non_public_event_gives_no_preview_at_all(monkeypatch, page_dir, path):
    client, _ = _client(monkeypatch, None)   # public_event ne rend rien : sur invitation, groupe, brouillon…
    r = client.get(path)
    assert r.status_code == 200
    assert "og:title" not in r.text and "og:description" not in r.text


def test_base_down_still_serves_the_page_without_preview(monkeypatch, page_dir):
    client, _ = _client(monkeypatch, PUBLIC, status=500)
    r = client.get(f"/events/event/{EVENT}")
    assert r.status_code == 200 and "og:title" not in r.text


def test_cancelled_public_event_says_so_and_other_pages_never_ask_the_base(monkeypatch, page_dir):
    client, seen = _client(monkeypatch, {**PUBLIC, "title": "Raclette", "status": "cancelled"})
    assert 'content="Annulé : Raclette"' in client.get(f"/events/event/{EVENT}").text
    seen.clear()
    for path in ("/events/groups", f"/events/event/{EVENT}/invite", "/events/event/pas-un-id", "/?tab=events",
                 "/?tab=events&event=pas-un-id", "/"):
        assert "og:title" not in client.get(path).text, path
    assert not any(p.endswith("/public_event") for p, _, _ in seen)


def test_event_id_is_recognised_only_as_a_uuid():
    assert event_preview.event_id_of_page(f"event/{EVENT}") == EVENT
    assert event_preview.event_id_of_page(f"share/{EVENT.upper()}/") == EVENT
    assert event_preview.event_id_of_page(f"event/{EVENT}/invite") is None
    assert event_preview.event_id_of_page("event/../x") is None


def test_a_slow_base_never_holds_the_page(monkeypatch, page_dir):
    import httpx
    from app import accounts as accounts_mod

    def slow(request):
        raise httpx.ReadTimeout("base lente")
    seen = {}
    real = httpx.Client.request

    def spy(self, *a, **kw):
        seen["timeout"] = kw.get("timeout")
        return real(self, *a, **kw)
    monkeypatch.setattr(httpx.Client, "request", spy)
    monkeypatch.setattr(main, "accounts", accounts_mod.Accounts(b"s", httpx.Client(transport=httpx.MockTransport(slow))))
    r = TestClient(main.app).get(f"/events/share/{EVENT}")
    assert r.status_code == 200 and "og:title" not in r.text
    assert seen["timeout"] == event_preview.LOOKUP_TIMEOUT <= 2


def test_the_event_poster_is_the_preview_image_when_there_is_one(monkeypatch, page_dir):
    """Restes de la campagne 2 : public_event rend l'affiche (https seulement) ; elle devient l'image de l'aperçu."""
    cover = "https://example.supabase.co/storage/v1/object/public/event-covers/a.jpg?v=1&x=\"2\""
    client, _ = _client(monkeypatch, {**PUBLIC, "cover_url": cover})
    page = client.get(f"/events/event/{EVENT}").text
    escaped = cover.replace("&", "&amp;").replace('"', "&quot;")
    assert f'property="og:image" content="{escaped}"' in page
    assert f'name="twitter:image" content="{escaped}"' in page
    assert 'name="twitter:card" content="summary_large_image"' in page
    assert "icon-512.png" not in page and 'og:image:width' not in page


@pytest.mark.parametrize("cover", [None, "", "event-covers/a.jpg", "http://example.com/a.jpg", "javascript:alert(1)"])
def test_without_a_safe_poster_the_party_icon_stays(monkeypatch, page_dir, cover):
    client, _ = _client(monkeypatch, {**PUBLIC, "cover_url": cover})
    page = client.get(f"/events/event/{EVENT}").text
    assert 'property="og:image" content="https://party.bobycharbon.ch/static/icon-512.png"' in page
    assert 'name="twitter:card" content="summary"' in page and 'og:image:width" content="512"' in page
