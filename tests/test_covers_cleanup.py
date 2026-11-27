"""Contrôle Apple tour 6 : la couverture créée par l'assistant IA (capture, image de la page) ou par « Changer la
couverture » part avec son événement (app/covers.py, registre covers/index.json). Politique : « elle est effacée avec lui »."""
import io

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.covers import UNUSED_AFTER, Covers

PUBLIC = "https://party.example"
EV1, EV2 = "e1e1e1e1-0000-4000-8000-000000000001", "e2e2e2e2-0000-4000-8000-000000000002"
ME, OTHER = "aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002"


def image(color) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(out, "PNG")
    return out.getvalue()


def file_of(covers: Covers, url: str):
    return covers.dir / url.rsplit("/", 1)[1]


def test_a_cover_never_put_on_an_event_goes_after_a_day(tmp_path):
    c = Covers(tmp_path, PUBLIC)
    draft = c.keep(image("red"))  # brouillon de l'assistant abandonné
    used = c.keep(image("blue"))
    c.attach(used, EV1, ME)
    assert c.purge() == 0 and file_of(c, draft).exists()
    import time
    assert c.purge(time.time() + UNUSED_AFTER + 1) == 1
    assert not file_of(c, draft).exists() and file_of(c, used).exists()


def test_a_replaced_or_removed_cover_is_erased_when_no_event_uses_it(tmp_path):
    c = Covers(tmp_path, PUBLIC)
    first, shared = c.keep(image("red")), c.keep(image("green"))
    c.attach(first, EV1, ME)
    c.attach(shared, EV2, ME)
    c.attach(shared, EV1, ME)  # EV1 change de couverture : la première part, la partagée reste (EV2)
    assert not file_of(c, first).exists() and file_of(c, shared).exists()
    c.attach(None, EV1, ME)  # « Retirer » sur EV1 : EV2 l'utilise encore
    assert file_of(c, shared).exists()
    c.attach(None, EV2, ME)
    assert not file_of(c, shared).exists()


def test_a_deleted_event_takes_its_cover_only_for_its_creator_and_an_old_file_is_never_touched(tmp_path):
    c = Covers(tmp_path, PUBLIC)
    url = c.keep(image("red"))
    c.attach(url, EV1, ME)
    assert c.release(EV1, OTHER) == 0 and file_of(c, url).exists()  # jamais sur la demande d'un autre
    assert c.release(EV1, ME) == 1 and not file_of(c, url).exists()
    legacy = c.dir / ("0" * 24 + ".jpg")  # fichier d'avant le registre
    legacy.write_bytes(b"x")
    c.attach(f"{PUBLIC}/covers/{legacy.name}", EV2, ME)
    assert c.release(EV2, ME) == 0 and c.purge(10**12) == 0 and legacy.exists()


def test_deleting_the_account_erases_the_covers_of_its_events(tmp_path):
    c = Covers(tmp_path, PUBLIC)
    mine, theirs = c.keep(image("red")), c.keep(image("blue"))
    c.attach(mine, EV1, ME)
    c.attach(theirs, EV2, OTHER)
    assert c.forget_owner(ME) == 1 and not file_of(c, mine).exists() and file_of(c, theirs).exists()
    assert main.local_stores().covers_forget.__self__ is main.covers


def test_the_event_page_tells_the_server_after_a_deletion(tmp_path, monkeypatch):
    c = Covers(tmp_path, main.PUBLIC_URL)
    url = c.keep(image("red"))
    c.attach(url, EV1, ME)
    monkeypatch.setattr(main, "covers", c)
    monkeypatch.setattr(main.accounts, "_uid", lambda token: ME)
    rows = {"value": [{"id": EV1}]}
    monkeypatch.setattr(main.accounts, "_get", lambda method, path, token, **kw: httpx.Response(200, json=rows["value"]))
    client = TestClient(main.app)
    # Encore là pour la base : rien n'est effacé.
    assert client.post("/api/account/event-cover/deleted", json={"token": "t", "event_id": EV1}).json() == {"removed": 0}
    assert file_of(c, url).exists()
    rows["value"] = []
    assert client.post("/api/account/event-cover/deleted", json={"token": "t", "event_id": EV1}).json() == {"removed": 1}
    assert not file_of(c, url).exists()
    page = open("web/events/src/app/event/[id]/index.tsx", encoding="utf-8").read()
    assert page.count("void coverDeleted(ev.id);") == 2


def test_the_assistant_ties_its_capture_cover_to_the_event_it_creates(tmp_path):
    from tests.test_ai_events import READY, make
    a, _, _ = make(tmp_path)
    a.covers = Covers(tmp_path, PUBLIC)
    url = a.covers.keep(image("red"))  # première capture devenue couverture
    a.create("ok", {**READY, "cover_url": url}, None)
    assert a.covers._index()[url.rsplit("/", 1)[1]]["events"] == {"e1": "u1"}
    assert a.covers.release("e1", "u1") == 1 and not file_of(a.covers, url).exists()


def test_the_privacy_policy_says_the_capture_goes_with_the_event():
    line = "La première capture peut devenir la couverture de l’événement ; elle est effacée avec lui."
    assert line in open("web/events/src/app/privacy.tsx", encoding="utf-8").read()
    assert line.replace("’", "'") in open("ios/Party/Settings/Account/SignInView.swift", encoding="utf-8").read()
