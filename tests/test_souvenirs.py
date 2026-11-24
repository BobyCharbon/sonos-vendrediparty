"""Souvenirs (avis 74d36b93e7bd, 24.11.2026) : le serveur (photo nettoyée : EXIF / GPS retirés, 1600 px, JPEG ; dépôt
puis souvenir_take ; fichier retiré si la base refuse), le relais (liste blanche, liens signés), l'IA qui n'allume
jamais l'option, et la migration (additive, rejouable, sans copie des photos gardées). La base est testée pour de vrai
dans tests/supabase_live/test_souvenirs_live.py."""
import io
import os
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


def phone_photo(w=4032, h=3024, fmt="JPEG") -> bytes:
    """Photo d'iPhone : EXIF avec position GPS, numéro de série, propriétaire, orientation (6 = tournée), date de prise."""
    img = Image.new("RGB", (w, h), (200, 30, 90))
    for x in range(0, w, 97):  # du détail, pour que l'image ne soit pas unie
        img.paste((x % 255, 120, 255 - x % 255), (x, 0, min(w, x + 40), h))
    exif = Image.Exif()
    exif[0x0112] = 6                       # orientation
    exif[0x010F] = "Apple"                 # fabricant
    exif[0x0110] = "iPhone 17 Pro"         # modèle
    exif[0x8769] = {0x9003: "2026:11:21 23:15:00", 0x9011: "+01:00", 0xA431: "SN-DQ12345678", 0xA430: "Ludo",
                    0xA435: "LENS-9876"}
    exif[0x8825] = {1: "N", 2: (46.0, 13.0, 0.0), 3: "E", 4: (7.0, 21.0, 0.0)}  # GPS (Sion)
    out = io.BytesIO()
    img.save(out, fmt, exif=exif, quality=92)
    return out.getvalue()


def sos(data: bytes) -> bytes:
    """Les octets de l'image : de l'en-tête SOS (FFDA) à la fin."""
    i = 2
    while data[i + 1] != 0xDA:
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return data[i:]


def test_the_original_loses_gps_and_serial_numbers_and_keeps_its_image_bytes_date_and_orientation():
    raw = phone_photo()
    assert b"SN-DQ12345678" in raw and b"LENS-9876" in raw
    original, _ = souvenirs.prepare(raw)
    assert sos(original) == sos(raw)  # pixels jamais réencodés : identiques à l'octet près
    assert b"SN-DQ12345678" not in original and b"LENS-9876" not in original and b"Ludo" not in original
    with Image.open(io.BytesIO(original)) as img:
        exif = img.getexif()
        assert img.size == (4032, 3024) and exif[0x0112] == 6 and exif[0x010F] == "Apple"
        assert 0x8825 not in exif and not exif.get_ifd(0x8825)
        sub = exif.get_ifd(0x8769)
        assert sub[0x9003] == "2026:11:21 23:15:00" and sub[0x9011] == "+01:00"
        assert not any(t in sub for t in (0xA430, 0xA431, 0xA435))


def test_a_broken_exif_falls_back_to_orientation_and_date_only():
    raw = phone_photo(400, 300)
    real, calls = Image.Exif.tobytes, []

    def flaky(self, *args, **kw):  # 1re écriture ratée (EXIF exotique) : seul l'essentiel reste
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("abîmé")
        return real(self, *args, **kw)

    with mock.patch.object(Image.Exif, "tobytes", flaky):
        original, _ = souvenirs.prepare(raw)
    assert sos(original) == sos(raw) and b"Apple" not in original and b"SN-DQ" not in original
    with Image.open(io.BytesIO(original)) as img:
        exif = img.getexif()
        assert set(exif) == {0x0112, 0x8769} and exif[0x0112] == 6 and set(exif.get_ifd(0x8769)) == {0x9003, 0x9011}


def test_the_screen_version_is_upright_2048_px_without_metadata():
    _, screen = souvenirs.prepare(phone_photo())
    with Image.open(io.BytesIO(screen)) as img:
        assert img.format == "JPEG" and img.size == (1536, 2048)   # orientation 6 appliquée : portrait
        assert not img.getexif()
    assert b"Apple" not in screen and b"SN-DQ" not in screen


def test_a_png_becomes_a_jpeg_and_anything_else_is_refused():
    out = io.BytesIO()
    Image.new("RGBA", (300, 200), (0, 0, 0, 0)).save(out, "PNG")
    original, screen = souvenirs.prepare(out.getvalue())
    for data in (original, screen):
        with Image.open(io.BytesIO(data)) as img:
            assert img.size == (300, 200) and img.format == "JPEG"
    for bad in (b"not an image", b"GIF89a" + b"\0" * 50, b"\xff\xd8\xff\xe1\x00"):
        with pytest.raises(ValueError, match="illisible"):
            souvenirs.prepare(bad)


@pytest.fixture
def disk(tmp_path, monkeypatch):
    monkeypatch.setattr(main.souvenir_service.files, "root", tmp_path)
    return main.souvenir_service.files


def test_after_seven_days_the_original_becomes_2560_px_high_quality(disk, monkeypatch):
    original, screen = souvenirs.prepare(phone_photo())
    disk.write(TICKET["path"], original, screen)
    v = disk.variants(TICKET["path"])
    assert v["original"].read_bytes() == original and v["screen"].read_bytes() == screen and not v["kept"].exists()
    assert disk.shrink_old() == 0  # tout juste prise
    monkeypatch.setenv(souvenirs.ORIGINAL_DAYS_ENV, "7")
    eight_days = __import__("time").time() - 8 * 86400
    os.utime(v["original"], (eight_days, eight_days))
    assert disk.shrink_old() == 1 and not v["original"].exists()
    with Image.open(v["kept"]) as img:
        assert img.size == (1920, 2560) and img.getexif().get_ifd(0x8769)[0x9003] == "2026:11:21 23:15:00"
        assert 0x8825 not in img.getexif()
    assert disk.find(TICKET["path"], "original") == v["kept"] and disk.find(TICKET["path"], "screen") == v["screen"]


def test_the_number_of_days_of_the_original_is_a_setting(monkeypatch):
    monkeypatch.setenv(souvenirs.ORIGINAL_DAYS_ENV, "3")
    assert souvenirs.original_days() == 3
    monkeypatch.setenv(souvenirs.ORIGINAL_DAYS_ENV, "n'importe quoi")
    assert souvenirs.original_days() == 7


KEY = "cle-du-serveur-souvenirs-pour-les-tests-0123456789"
PHOTO = "0a0b0c0d-0000-4000-8000-0000000000ff"
TICKET = {"id": PHOTO, "path": f"{EVENT}/{ME}/{PHOTO}.jpg"}


def answers(*replies):
    """Réponses successives de la base (souvenir_upload_ticket, puis souvenir_take…)."""
    return mock.patch.object(souvenirs.Db, "call", side_effect=list(replies))


def test_upload_gets_a_ticket_then_souvenir_take_then_writes_original_and_screen_on_the_disk(client, disk, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    taken = {"id": PHOTO, "path": TICKET["path"], "taken": 1, "left": 2, "cancel_until": "2026-11-24T22:00:05Z"}
    raw = phone_photo(800, 600)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(main.accounts, "_get") as storage, \
            answers((200, TICKET), (200, taken)) as call:
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=raw,
                        headers={"Authorization": "Bearer t", "Content-Type": "image/jpeg"})
    assert r.status_code == 200 and r.json() == taken
    assert storage.call_count == 0  # plus rien dans Supabase Storage
    assert [c.args for c in call.call_args_list] == [("souvenir_upload_ticket", {"e": EVENT, "p_key": KEY}, "t"),
                                                     ("souvenir_take", {"e": EVENT, "id": PHOTO}, "t")]
    v = disk.variants(TICKET["path"])
    assert sos(v["original"].read_bytes()) == sos(raw) and b"SN-DQ" not in v["original"].read_bytes()
    with Image.open(v["screen"]) as img:
        assert img.size == (600, 800)


def test_a_refused_photo_leaves_nothing_on_the_disk_and_the_words_of_the_database_are_kept(client, disk, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), \
            answers((200, TICKET), (400, {"message": "full: tu as déjà pris tes 3 photos"})):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 409 and r.json() == {"code": "full", "detail": "tu as déjà pris tes 3 photos"}
    assert not any(disk.root.rglob("*.jpg"))


def test_a_disk_failure_cancels_the_photo_in_the_database(client, disk, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), mock.patch.object(disk, "write", side_effect=OSError("plein")), \
            answers((200, TICKET), (200, {"id": PHOTO}), (200, {"cancelled": True})) as call:
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 400 and "pas pu être enregistrée" in r.json()["detail"]
    assert call.call_args_list[-1].args == ("souvenir_cancel", {"id": PHOTO}, "t")


def test_a_refused_ticket_writes_nothing(client, disk, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), \
            answers((400, {"message": "closed: l'appareil photo est ouvert du début de l'événement à 2 h après sa fin"})) as call:
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 409 and r.json()["code"] == "closed" and call.call_count == 1 and not any(disk.root.rglob("*"))


def test_without_the_server_key_or_with_a_wrong_one_the_camera_is_not_ready(client, disk, monkeypatch):
    """Sans SOUVENIRS_SECRET (ou refusée par la base) : panne de configuration, 503, rien n'est écrit."""
    monkeypatch.delenv(souvenirs.SECRET_ENV, raising=False)
    with mock.patch.object(main.accounts, "_uid", return_value=ME), answers() as call:
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 503 and "pas encore prêt" in r.json()["detail"] and call.call_count == 0
    monkeypatch.setenv(souvenirs.SECRET_ENV, "fausse-cle-0123456789-0123456789-0123")
    with mock.patch.object(main.accounts, "_uid", return_value=ME), \
            answers((400, {"message": "server: les photos passent par le serveur de Party"})):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=phone_photo(400, 300),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 503 and not any(disk.root.rglob("*.jpg"))


def test_upload_needs_a_session_a_valid_event_a_real_photo_and_at_most_25_mb(client):
    assert client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=b"x").status_code == 401
    assert client.post("/api/account/souvenirs/photo?event_id=../x", content=b"x",
                       headers={"Authorization": "Bearer t"}).status_code == 400
    with mock.patch.object(main.accounts, "_uid", return_value=ME):
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=b"pas une photo",
                        headers={"Authorization": "Bearer t"})
        assert r.status_code == 400 and "illisible" in r.json()["detail"]
        r = client.post(f"/api/account/souvenirs/photo?event_id={EVENT}", content=b"\xff" * (souvenirs.RAW_MAX + 1),
                        headers={"Authorization": "Bearer t"})
    assert r.status_code == 413 and "25 Mo" in r.json()["detail"]


def test_the_relay_only_calls_souvenir_functions(client):
    with mock.patch.object(souvenirs.Db, "call", return_value=(200, {"enabled": False})) as call:
        for fn in ("prono_list", "souvenir_take", "souvenir_upload_ticket", "souvenir_files_gc", "souvenir_readable",
                   "souvenir_trash_take", "souvenir_trash_done"):
            assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": fn}).status_code == 404, fn
        assert client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "report_content",
                                                                "args": {"p_kind": "profile"}}).status_code == 404
        assert call.call_count == 0
        r = client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_counter", "args": {"e": EVENT}})
    assert r.json() == {"result": {"enabled": False}}


A = f"{EVENT}/{ME}/0a0b0c0d-0000-4000-8000-00000000000a.jpg"
GONE = f"{EVENT}/{ME}/0a0b0c0d-0000-4000-8000-00000000000b.jpg"


def test_story_photos_get_server_links_only_when_the_database_lets_me_read_them(client):
    story = {"photos": [{"id": "1", "path": A, "author": {"id": ME, "name": "Léa", "avatar_url": "a/p.png"}},
                        {"id": "2", "path": GONE, "author": {"id": ME, "name": "Léa", "avatar_url": None}}]}

    def db(name, args, token):
        if name == "souvenir_readable":  # la base décide, avec MON jeton
            assert token == "t" and sorted(args["paths"]) == sorted([A, GONE])
            return 200, [A]
        return 200, story

    def faces(method, path, token, **kw):
        assert path == "/storage/v1/object/sign/profile-photos"
        return mock.Mock(status_code=200, json=lambda: [{"path": "a/p.png", "signedURL": "/object/sign/profile-photos/a/p.png?token=x"}])

    with mock.patch.object(souvenirs.Db, "call", side_effect=db), mock.patch.object(main.accounts, "_get", side_effect=faces):
        out = client.post("/api/account/souvenirs/rpc", json={"token": "t", "fn": "souvenir_story", "args": {"e": EVENT}}).json()["result"]
    one, two = out["photos"]
    assert one["url"].startswith("/api/souvenirs/file/") and one["url"].endswith("?v=screen")
    assert one["original"].endswith("?v=original")
    assert two["url"] is None and two["original"] is None  # droit refusé : aucun lien
    assert one["author"]["photo"].endswith("/profile-photos/a/p.png?token=x")


def test_a_signed_link_serves_the_file_privately_with_an_etag_and_expires(client, disk):
    original, screen = souvenirs.prepare(phone_photo(800, 600))
    disk.write(A, original, screen)
    links = main.souvenir_service.links
    url = links.url(A, "screen")
    r = client.get(url)
    assert r.status_code == 200 and r.content == screen and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"].startswith("private") and r.headers["etag"]
    assert client.get(url, headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    r = client.get(links.url(A, "original") + "&download=souvenir-2026-11-21.jpg")
    assert r.content == original and 'attachment; filename="souvenir-2026-11-21.jpg"' == r.headers["content-disposition"]
    # Expiré (10 à 15 min), falsifié, ou vers un autre chemin : refusé.
    old = links.token(A, now=__import__("time").time() - 16 * 60)
    assert client.get(f"/api/souvenirs/file/{old}?v=screen").status_code == 403
    raw, sig = links.token(A).split(".")
    forged = souvenirs._b64(souvenirs._unb64(raw).replace(b"00a", b"00b")) + "." + sig
    assert client.get(f"/api/souvenirs/file/{forged}?v=screen").status_code == 403
    other = souvenirs.Links(b"une autre cle").token(A)
    assert client.get(f"/api/souvenirs/file/{other}?v=screen").status_code == 403
    assert client.get(links.url(GONE)).status_code == 404
    assert links.check(links.token("../../etc/passwd")) is None


def test_moderation_links_ask_the_database_first(client):
    with mock.patch.object(souvenirs.Db, "call", return_value=(200, [A])) as call:
        r = client.post("/api/account/souvenirs/links", json={"token": "t", "paths": [A, GONE, "../x"]})
    assert list(r.json()["links"]) == [A] and call.call_args.args[0] == "souvenir_readable"
    assert sorted(call.call_args.args[1]["paths"]) == sorted([A, GONE])  # un chemin piégé n'est même pas demandé
    with mock.patch.object(souvenirs.Db, "call", return_value=(200, [])):
        assert client.post("/api/account/souvenirs/links", json={"token": "t", "paths": [A]}).json() == {"links": {}}


def test_the_trash_of_the_database_erases_the_files_from_the_disk(disk, monkeypatch):
    monkeypatch.setenv(souvenirs.SECRET_ENV, KEY)
    original, screen = souvenirs.prepare(phone_photo(400, 300))
    disk.write(A, original, screen)
    disk.write(GONE, original, screen)
    calls = []

    def db(name, args, token=None):
        calls.append((name, args))
        return (200, [A, "../../etc/passwd"]) if name == "souvenir_trash_take" else (200, 2)

    with mock.patch.object(souvenirs.Db, "call", side_effect=db):
        assert main.souvenir_service.empty_trash() == 2
    assert not any(disk.variants(A)[k].exists() for k in ("original", "screen", "kept"))
    assert disk.variants(GONE)["original"].exists()  # pas dans la corbeille : gardée
    assert calls == [("souvenir_trash_take", {"p_key": KEY, "n": 200}),
                     ("souvenir_trash_done", {"p_key": KEY, "paths": [A, "../../etc/passwd"]})]


def test_the_admin_sees_photos_size_and_last_nas_copy(client, disk):
    original, screen = souvenirs.prepare(phone_photo(400, 300))
    disk.write(A, original, screen)
    (disk.root / souvenirs.NAS_STAMP).write_text("2026-11-24T03:00:02+01:00\n")
    assert disk.stats() == {"photos": 1, "bytes": len(original) + len(screen), "nas": "2026-11-24T03:00:02+01:00"}
    assert client.get("/api/admin/souvenirs").status_code == 401  # admin seulement


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


def test_the_disk_migration_is_additive_and_leaves_the_trash_to_the_server():
    """20261124150000 : fichiers sur le disque du serveur ; le ticket reste la seule porte ; la base ne vide plus la corbeille."""
    disk = (ROOT / "supabase/migrations/20261124150000_souvenirs_disque.sql").read_text(encoding="utf-8")
    assert not any(w in disk.lower() for w in ("drop table", "drop column", "truncate", "drop policy", "drop function"))
    take = re.search(r"function public\.souvenir_take\(.*?end \$\$;", disk, re.S).group(0)
    assert "storage.objects" not in take and "souvenir_tickets" in take and "t.expires_at > now()" in take
    gc = re.search(r"function private\.souvenir_files_gc_now\(\).*?end \$\$;", disk, re.S).group(0)
    assert "souvenir_trash" not in gc  # la corbeille sert au serveur (disque + NAS)
    for fn in ("souvenir_trash_take", "souvenir_trash_done"):
        body = re.search(rf"function public\.{fn}\(.*?end \$\$;", disk, re.S).group(0)
        assert "private.souvenir_server_ok(p_key)" in body, fn
    assert "private.souvenir_may_read(x.p)" in disk
    assert "grant execute on function public.souvenir_readable(text[]) to authenticated" in disk


def test_the_admin_page_shows_the_souvenirs_line_on_the_settings():
    page = (ROOT / "app/static/admin.html").read_text(encoding="utf-8")
    assert 'id="souvenirsDisk"' in page and 'fetch("/api/admin/souvenirs"' in page
    assert "sur le serveur · dernière copie NAS : " in page and "loadSouvenirsDisk(); }" in page
