"""Souvenirs dans l'app iPhone (24.11) : textes d'autorisation (appareil photo, ajout à Photos), crochet de la recette
jamais dans la version de l'App Store, interrupteur « Souvenirs » accepté par le serveur, toucher des notifications
(story, relecture) et bulles des Discussions (attente au labo, story)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app import main

ROOT = Path(__file__).resolve().parents[1]
EVENT = "0a0b0c0d-0000-4000-8000-000000000024"


def test_camera_and_photos_texts_name_the_souvenirs():
    """BETA seulement : l'app App Store n'a pas les Souvenirs et ne les cite pas (contrôle Apple du 26.11)."""
    from tests.test_compliance_1411 import targets, usage_texts
    beta, store = usage_texts(targets()["Party"], "STORE_beta"), usage_texts(targets()["Party"])
    # 28.11 : la BETA (copie exacte de l'app App Store) n'a plus les Souvenirs : aucune des deux ne les cite.
    for key in ("NSCameraUsageDescription", "NSPhotoLibraryAddUsageDescription"):
        assert "Souvenirs" not in beta[key] and "Souvenirs" not in store[key]


def test_the_fake_camera_of_the_recette_never_reaches_the_app_store_build():
    """L'image de test qui remplace la caméra (simulateur) n'existe que dans DEBUG ou E2E_HOOKS."""
    src = (ROOT / "ios/Party/Souvenirs/SouvenirCamera.swift").read_text(encoding="utf-8")
    reads = src.split('environment["PARTY_E2E_SOUVENIR_CAMERA"]')
    assert len(reads) == 2  # une seule lecture du crochet
    before, after = reads
    assert before.rsplit("#if", 1)[1].startswith(" DEBUG || E2E_HOOKS") and "#endif" not in before.rsplit("#if", 1)[1]
    assert "#else" in after.split("#endif", 1)[0] and "return false" in after.split("#endif", 1)[0]
    assert "UIImagePickerController" not in src and "PHPicker" not in src  # jamais la Photothèque


def test_the_server_saves_the_souvenirs_notification_switch():
    assert main.NotificationPatch(souvenirs=False).model_dump(exclude_unset=True) == {"souvenirs": False}


@pytest.mark.skipif(not shutil.which("node"), reason="Node absent")
def test_web_push_opens_the_story_or_the_review():
    script = ("import(process.argv[1]).then(({ notificationTarget }) => "
              "console.log(JSON.stringify(JSON.parse(process.argv[2]).map(notificationTarget))))")
    rows = [{"origin": "https://party.bobycharbon.ch", "kind": k, "event_id": EVENT} for k in ("souvenirs_revealed", "souvenir_reported")]
    out = subprocess.run(["node", "-e", script, (ROOT / "supabase/functions/send-web-push/target.ts").as_uri(), json.dumps(rows)],
                         capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == [f"https://party.bobycharbon.ch/?tab=events&event={EVENT}&souvenirs=1",
                                      f"https://party.bobycharbon.ch/?tab=events&event={EVENT}&souvenirs=review"]


def test_apns_opens_the_story_or_the_review():
    apns = (ROOT / "supabase/functions/send-push/apns.ts").read_text(encoding="utf-8")
    assert "data.kind === 'souvenirs_revealed') return `/?tab=events&event=${event}&souvenirs=1`" in apns
    assert "data.kind === 'souvenir_reported') return `/?tab=events&event=${event}&souvenirs=review`" in apns


def test_bubbles_migration_is_additive_and_only_counts_while_waiting():
    sql = (ROOT / "supabase/migrations/20261124120000_souvenirs_bulles_attente.sql").read_text(encoding="utf-8")
    assert "create or replace function public.souvenir_stories()" in sql
    assert not any(w in sql.lower() for w in ("drop table", "drop column", "delete from", "truncate"))
    assert "x.ph in ('story', 'waiting')" in sql and "'phase', x.ph" in sql and "'reveal_at'" in sql
    # Pendant l'attente : le NOMBRE seulement (jamais d'auteur ni de chemin de photo).
    assert "'path'" not in sql and "'author'" not in sql and "souvenir_json" not in sql


def test_the_native_camera_takes_full_resolution_best_quality_and_sends_it_as_is():
    """Décision du 24.11 : l'original est gardé 7 jours par le serveur ; l'iPhone ne réduit plus rien."""
    src = (ROOT / "ios/Party/Souvenirs/SouvenirCamera.swift").read_text(encoding="utf-8")
    assert "output.maxPhotoQualityPrioritization = .quality" in src and "settings.photoQualityPrioritization = .quality" in src
    assert "output.maxPhotoDimensions = largest" in src and "settings.maxPhotoDimensions = output.maxPhotoDimensions" in src
    assert "AVVideoQualityKey: Self.quality" in src and "static let quality: Float = 0.95" in src
    assert "maxSide" not in src and "1600" not in src and "UIGraphicsImageRenderer(size: target" not in src
    assert "return raw.flatMap(Self.sendable)" in src


def test_the_app_reads_photos_from_the_party_server_and_keeps_the_seen_ones():
    models = (ROOT / "ios/Party/Souvenirs/SouvenirsModels.swift").read_text(encoding="utf-8")
    assert 'url.path.hasPrefix("/api/souvenirs/file/")' in models and "storage/v1" not in models
    store = (ROOT / "ios/Party/Souvenirs/SouvenirsStore.swift").read_text(encoding="utf-8")
    assert "SouvenirImageCache.shared.image(photo.id)" in store and "addResource(with: .photo, data: data" in store
    story = (ROOT / "ios/Party/Souvenirs/SouvenirStoryView.swift").read_text(encoding="utf-8")
    assert "await store.image(for: photo)" in story and "URLSession.shared" not in story
