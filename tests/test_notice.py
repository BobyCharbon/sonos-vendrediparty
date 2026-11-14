"""Message pour tout le monde (avis eb710b132330) : maintenance, information ou annonce, posé par l'admin ; et
« Mise à jour en cours » posé tout seul à chaque mise à jour du serveur, effacé quand il revient."""
import pytest
from fastapi.testclient import TestClient

from app import main, notice
from app.notice import AUTO_TTL, NoticeError, NoticeStore, make


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = NoticeStore(tmp_path / "notice.json")
    monkeypatch.setattr(main, "notices", s)
    return s


@pytest.fixture
def client(store):
    return TestClient(main.app)


@pytest.fixture
def admin(client):
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    return client


# ── Le message ──

@pytest.mark.parametrize("kind, title", [("maintenance", "Mise à jour en cours"), ("info", "Information"), ("announce", "Annonce")])
def test_each_kind_has_a_default_title(kind, title):
    assert make(kind, message="Texte").title == title


def test_a_maintenance_needs_no_text_but_information_and_announce_do():
    assert make("maintenance").message == ""
    for kind in ("info", "announce"):
        with pytest.raises(NoticeError, match="Écris le message"):
            make(kind, message="   ")


def test_unknown_kind_and_too_long_texts_are_refused():
    with pytest.raises(NoticeError):
        make("pub", message="x")
    with pytest.raises(NoticeError, match="280"):
        make("info", message="x" * 281)
    with pytest.raises(NoticeError, match="60"):
        make("info", title="x" * 61, message="ok")


def test_texts_are_tidied_control_characters_dropped():
    n = make("announce", title="  Soirée \n spéciale ", message="Ligne 1  \n\n\n\nLigne\t 2\x07")
    assert n.title == "Soirée spéciale"
    assert n.message == "Ligne 1\n\nLigne 2"


# ── Mise à jour du serveur ──

def test_a_deploy_shows_maintenance_and_the_restarted_server_clears_it(store):
    notice.deploy(store)
    n = store.current()
    assert n.kind == "maintenance" and n.auto and n.title == "Mise à jour en cours"
    assert store.clear_auto() is True
    assert store.current() is None


def test_a_deploy_keeps_the_admin_announcement_for_after(store):
    store.set(make("announce", message="Soirée raclette vendredi !"))
    notice.deploy(store)
    assert store.current().kind == "maintenance"
    store.clear_auto()
    assert store.current().message == "Soirée raclette vendredi !"


def test_an_admin_maintenance_wins_over_a_deploy_and_stays_after_it(store):
    store.set(make("maintenance", message="Retour à 18 h"))
    notice.deploy(store)
    assert store.current().message == "Retour à 18 h"
    store.clear_auto()
    assert store.current().message == "Retour à 18 h"


def test_a_forgotten_deploy_maintenance_disappears_on_its_own(store):
    n = notice.deploy(store)
    assert store.current(now=n.at + AUTO_TTL - 1) is not None
    assert store.current(now=n.at + AUTO_TTL + 1) is None


def test_the_deploy_command_writes_where_the_server_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert notice.main(["notice", "deploy"]) == 0
    assert NoticeStore(tmp_path / "notice.json").current().auto
    assert notice.main(["notice", "done"]) == 0
    assert NoticeStore(tmp_path / "notice.json").current() is None
    assert notice.main(["notice", "?"]) == 2


def test_a_change_written_by_another_process_is_seen(tmp_path):
    reader = NoticeStore(tmp_path / "notice.json")
    assert reader.current() is None
    NoticeStore(tmp_path / "notice.json").set(make("info", message="Bonjour"))
    assert reader.current().message == "Bonjour"


# ── L'API ──

def test_everyone_reads_the_notice_without_who_set_it(admin, store):
    assert admin.get("/api/notice").json() == {"notice": None}
    admin.post("/api/admin/notice", json={"kind": "announce", "message": "Ce soir : karaoké"})
    got = TestClient(main.app).get("/api/notice").json()["notice"]
    assert got["kind"] == "announce" and got["message"] == "Ce soir : karaoké" and got["title"] == "Annonce"
    assert "by" not in got and "at" not in got


def test_only_the_admin_sets_or_clears_it(client, store):
    assert client.post("/api/admin/notice", json={"kind": "info", "message": "x"}).status_code == 401
    assert client.delete("/api/admin/notice").status_code == 401
    assert client.get("/api/admin/notice").status_code == 401
    assert store.current() is None


def test_admin_sets_then_stops_the_message_and_it_is_journaled(admin, store):
    r = admin.post("/api/admin/notice", json={"kind": "maintenance", "message": "Retour à 18 h"})
    assert r.status_code == 200 and r.json()["notice"]["by"] == "Code PIN"
    assert admin.get("/api/admin/notice").json()["notice"]["message"] == "Retour à 18 h"
    assert admin.delete("/api/admin/notice").json() == {"notice": None}
    assert store.current() is None
    actions = [e["action"] for e in main.journal.read(limit=10)]
    assert "notice.set" in actions and "notice.clear" in actions


def test_a_refused_message_says_why(admin):
    r = admin.post("/api/admin/notice", json={"kind": "info", "message": ""})
    assert r.status_code == 400 and "Écris le message" in r.json()["detail"]
    assert admin.post("/api/admin/notice", json={"kind": "pub", "message": "x"}).status_code == 422


def test_every_api_answer_carries_the_notice_id(admin, store):
    assert admin.get("/api/features").headers["X-Party-Notice"] == ""
    n = notice.deploy(store)
    assert admin.get("/api/features").headers["X-Party-Notice"] == n.id
    assert "X-Party-Notice" not in admin.get("/static/style.css").headers
