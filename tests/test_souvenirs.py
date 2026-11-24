"""Souvenirs (avis 74d36b93e7bd, 24.11.2026) : le serveur (photo nettoyée : EXIF / GPS retirés, 1600 px, JPEG ; dépôt
puis souvenir_take ; fichier retiré si la base refuse), le relais (liste blanche, liens signés), l'IA qui n'allume
jamais l'option, et la migration (additive, rejouable, sans copie des photos gardées). La base est testée pour de vrai
dans tests/supabase_live/test_souvenirs_live.py."""
import io
import re
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import ai_events as ev
from app import main, souvenirs

ROOT = Path(__file__).resolve().parents[1]
EVENT = "0a0b0c0d-0000-4000-8000-000000000024"
ME = "0a0b0c0d-0000-4000-8000-0000000000aa"
SQL = (ROOT / "supabase/migrations/20261124090000_souvenirs.sql").read_text(encoding="utf-8")


@pytest.fixture
def client():
    return TestClient(main.app)


def phone_photo(w=4032, h=3024) -> bytes:
    """Photo d'iPhone : EXIF avec position GPS, orientation (6 = tournée), commentaire."""
    img = Image.new("RGB", (w, h), (200, 30, 90))
    exif = Image.Exif()
    exif[0x0112] = 6                       # orientation
    exif[0x010F] = "Apple"                 # fabricant
    exif[0x8825] = {1: "N", 2: (46.0, 13.0, 0.0), 3: "E", 4: (7.0, 21.0, 0.0)}  # GPS (Sion)
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif, comment=b"secret")
    return out.getvalue()


def test_the_photo_loses_exif_and_gps_is_turned_upright_and_reduced_to_1600_px():
    raw = phone_photo()
    assert b"Apple" in raw
    clean = souvenirs.clean_jpeg(raw)
    with Image.open(io.BytesIO(clean)) as img:
        assert img.format == "JPEG" and max(img.size) == 1600
        assert img.size == (1200, 1600)    # orientation 6 appliquée : portrait
        assert not img.getexif() and "exif" not in img.info and "comment" not in img.info and "icc_profile" not in img.info
    assert b"Apple" not in clean and b"secret" not in clean


def test_a_small_png_stays_small_and_anything_else_is_refused():
    out = io.BytesIO()
    Image.new("RGBA", (300, 200), (0, 0, 0, 0)).save(out, "PNG")
    with Image.open(io.BytesIO(souvenirs.clean_jpeg(out.getvalue()))) as img:
        assert img.size == (300, 200) and img.format == "JPEG"
    for bad in (b"not an image", b"GIF89a" + b"\0" * 50):
        with pytest.raises(ValueError, match="illisible"):
            souvenirs.clean_jpeg(bad)


KEY = "cle-du-serveur-souvenirs-pour-les-tests-0123456789"
PHOTO = "0a0b0c0d-0000-4000-8000-0000000000ff"
TICKET = {"id": PHOTO, "path": f"{EVENT}/{ME}/{PHOTO}.jpg"}


def answers(*replies):
    """Réponses successives de la base (souvenir_upload_ticket, puis souvenir_take)."""
    return mock.patch.object(souvenirs.Db, "call", side_effect=list(replies))


def test_upload_gets_a_ticket_with_the_server_key_puts_the_clean_file_then_calls_souvenir_take(client, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    calls = []

    def fake_get(method, path, token, **kw):
        calls.append((method, path, kw))
        return mock.Mock(status_code=200, json=lambda: {})

    taken = {"id": PHOTO, "path": TICKET["path"], "taken": 1, "left": 2, "cancel_until": "2026-11-24T22:00:05Z"}
    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(main.accounts, "_get", side_effect=fake_get), \
            answers((200, TICKET), (200, taken)) as call:
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(800, 600),
                        headers={"Authorization": "Bearer t", "Content-Type": "image/jpeg"})
    assert r.status_code == 200 and r.json() == taken
    method, path, kw = calls[0]
    assert method == "POST" and path == f"/storage/v1/object/souvenirs/{TICKET['path']}"
    assert kw["headers"]["Content-Type"] == "image/jpeg" and b"Apple" not in kw["content"]
    assert [c.args for c in call.call_args_list] == [("souvenir_upload_ticket", {"e": EVENT, "p_key": KEY}, "t"),
                                                     ("souvenir_take", {"e": EVENT, "id": PHOTO}, "t")]


def test_a_refused_photo_is_removed_and_the_words_of_the_database_are_kept(client, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    calls = []

    def fake_get(method, path, token, **kw):
        calls.append((method, path))
        return mock.Mock(status_code=200, json=lambda: {})

    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(main.accounts, "_get", side_effect=fake_get), \
            answers((200, TICKET), (400, {"message": "full: tu as déjà pris tes 3 photos"})):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 409 and r.json() == {"code": "full", "detail": "tu as déjà pris tes 3 photos"}
    assert [m for m, _ in calls] == ["POST", "DELETE"] and calls[0][1] == calls[1][1]


def test_a_refused_ticket_uploads_nothing(client, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(main.accounts, "_get") as get, \
            answers((400, {"message": "closed: l'appareil photo est ouvert du début de l'événement à 2 h après sa fin"})):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 409 and r.json()["code"] == "closed" and get.call_count == 0


def test_without_the_server_key_or_with_a_wrong_one_the_camera_is_not_ready(client, monkeypatch):
    """Sans SOUVENIRS_SECRET (ou refusée par la base) : panne de configuration, 503, rien n'est déposé."""
    monkeypatch.delenv(souvenirs.SECRET_ENV, raising=False)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(main.accounts, "_get") as get, \
            answers() as call:
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 503 and "pas encore prêt" in r.json()["detail"] and get.call_count == 0 and call.call_count == 0
    monkeypatch.setenv(souvenirs.SECRET_ENV, "fausse-cle-0123456789-0123456789-0123")
    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(main.accounts, "_get") as get, \
            answers((400, {"message": "server: les photos passent par le serveur de Party"})):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 503 and get.call_count == 0


def test_upload_needs_a_session_a_valid_event_and_a_real_photo(client):
    assert client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=b"x").status_code == 401
    assert client.post("/api/account/souvenirs/photo?event_id=../x", content=b"x",
                       headers={"Authorization": "Bearer t"}).status_code == 400
    with mock.patch.object(main.accounts, "_uid", return_value=ME):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=b"pas une photo",
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 400 and "illisible" in r.json()["detail"]


def test_the_relay_only_calls_souvenir_functions(client):
    with mock.patch.object(souvenirs.Db, "call", return_value=(200, {"enabled": False})) as call:
        assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "prono_list"}).status_code == 404
        assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_take"}).status_code == 404
        assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_upload_ticket"}).status_code == 404
        assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_files_gc"}).status_code == 404
        assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "report_content",
                                                                "args": {"p_kind": "profile"}}).status_code == 404
        assert call.call_count == 0
        r = client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_counter", "args": {"e": EVENT}})
    assert r.json() == {"result": {"enabled": False}}


def test_story_photos_and_authors_get_short_signed_links(client):
    story = {"photos": [{"id": "1", "path": f"{EVENT}/{ME}/a.jpg", "author": {"id": ME, "name": "Léa", "avatar_url": "a/p.png"}},
                        {"id": "2", "path": f"{EVENT}/{ME}/gone.jpg", "author": {"id": ME, "name": "Léa", "avatar_url": None}}]}
    seen = []

    def fake_get(method, path, token, **kw):
        seen.append((path, kw["json"]["expiresIn"]))
        bucket = path.rsplit("/", 1)[1]
        rows = [{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?token=x"} for p in kw["json"]["paths"] if "gone" not in p]
        return mock.Mock(status_code=200, json=lambda: rows)

    with mock.patch.object(souvenirs.Db, "call", return_value=(200, story)), mock.patch.object(main.accounts, "_get", side_effect=fake_get):
        out = client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_story", "args": {"e": EVENT}}).json()["result"]
    assert out["photos"][0]["url"].endswith(f"/storage/v1/object/sign/souvenirs/{EVENT}/{ME}/a.jpg?token=x")
    assert out["photos"][1]["url"] is None  # plus montrée : pas de lien
    assert out["photos"][0]["author"]["photo"].endswith("/profile-photos/a/p.png?token=x")
    assert all(ttl == souvenirs.SIGNED_TTL <= 600 for _, ttl in seen)


def test_refusals_keep_their_code(client):
    for message, status in (("too_early: on ne dévoile jamais avant la fin de l'événement", 409),
                            ("locked: les réglages des Souvenirs sont figés depuis la première photo", 409),
                            ("terms_required: accepte les CGU", 403), ("forbidden: organisation seulement", 403)):
        with mock.patch.object(souvenirs.Db, "call", return_value=(400, {"message": message})):
            r = client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_reveal_now", "args": {"e": EVENT}})
        assert r.status_code == status and r.json()["code"] == message.split(":")[0]


def test_the_ai_never_turns_souvenirs_on():
    """Comme les billets QR et le covoiturage : hors du schéma, du brouillon et de l'événement écrit."""
    schema = ev.schema({"categories": [], "tags": [], "audiences": ["Vendredi Party"], "people": []})
    assert "souvenir" not in str(schema).lower()
    d = ev.clean_draft({"title": "Raclette", "souvenirs_enabled": True, "souvenirs_keep": False, "souvenirs": True},
                       datetime.now(ev.ZURICH), {"categories": [], "tags": [], "audiences": [], "people": []})
    assert not any("souvenir" in k for k in d)
    for module in ("app/ai_events.py", "app/ai_event_edit.py"):
        assert "souvenir" not in (ROOT / module).read_text(encoding="utf-8").lower()


def test_the_migration_is_additive_and_keeps_only_references():
    assert "drop table" not in SQL.lower() and "drop column" not in SQL.lower()
    for line in re.findall(r"(?im)^\s*(alter table [^;]+add column[^;]+;)", SQL):
        assert "if not exists" in line, line
    for name in re.findall(r"(?im)^create trigger (\w+) ", SQL):
        assert f"drop trigger if exists {name} " in SQL, name
    for name in re.findall(r"(?im)^create policy \"([^\"]+)\"", SQL):
        assert f'drop policy if exists "{name}"' in SQL, name
    # Gardée = une référence (photo, personne), jamais une copie du fichier ni du chemin.
    keeps = re.search(r"create table if not exists public\.souvenir_keeps \((.*?)\n\);", SQL, re.S).group(1)
    assert "path" not in keeps and "references public.souvenir_photos (id) on delete cascade" in keeps
    # Ni « Je suis sur cette photo » ni partage : le droit à l'image passe par Signaler (motif my_image).
    assert "im_on_it" not in SQL and "souvenir_share" not in SQL and "souvenirs_review" not in SQL
    assert "'my_image'" in SQL and "''souvenir''::text" in SQL
    assert "souvenirs_keep boolean not null default true" in SQL and "souvenirs_enabled boolean not null default false" in SQL
    assert "cron.schedule('souvenirs-tick'" in SQL and "interval '13 months'" in SQL


def test_moderators_can_read_the_new_kind_and_reason():
    from app import moderation_api
    assert "souvenir" in moderation_api.KINDS and "my_image" in moderation_api.REASONS


def test_the_common_sense_migration_is_additive_and_covers_each_point():
    """Contrôle « bon sens » (24.11, 20261124130000) ; la base est testée pour de vrai dans test_souvenirs_live.py."""
    fix = (ROOT / "supabase/migrations/20261124130000_souvenirs_bon_sens.sql").read_text(encoding="utf-8")
    assert "drop table" not in fix.lower() and "drop column" not in fix.lower()
    for name in re.findall(r"(?im)^create trigger (\w+) ", fix):
        assert f"drop trigger if exists {name} " in fix, name
    guard = re.search(r"function private\.souvenirs_guard\(\).*?end \$\$;", fix, re.S).group(0)
    # 1. Récurrents : remise à zéro à l'insertion AVANT tout test de rôle (spawn_series tourne en postgres).
    assert guard.index("if tg_op = 'INSERT'") < guard.index("current_user")
    # 2. Remettre : jamais sa photo, jamais un « my_image » ouvert.
    restore = re.search(r"function public\.souvenir_restore\(.*?end \$\$;", fix, re.S).group(0)
    assert "p.author_id = me" in restore and "souvenir_my_image_open" in restore
    # 3. Annulé : ni dévoilement ni notification.
    assert "ev.status <> 'published' then return 0" in fix and "x.status = 'published'" in fix
    # 4. Date déplacée : le dévoilement posé avant la nouvelle fin est retiré.
    assert "new.souvenirs_reveal_at := null" in guard.split("Date déplacée")[1]
    # 5. Rafale : 5 photos masquées au plus par personne et par soirée.
    assert ">= 5 then" in fix
    # 6. Sans « garder » : la notification dit que les photos disparaissent.
    assert "puis elles disparaissent." in fix
    # 7. Réponse après la fin : pas de story (sauf photo prise ou organisation).
    assert "private.souvenir_late" in fix and "private.souvenir_viewer(e, me)" in fix
