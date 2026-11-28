"""tools/appstore_submit.py : envoi des captures App Store (découpage selon Apple, nombre de captures exigé)."""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
pytest.importorskip("cryptography")
spec = importlib.util.spec_from_file_location("appstore_submit", ROOT / "tools/appstore_submit.py")
appstore_submit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(appstore_submit)


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b""


def test_each_upload_operation_sends_its_own_slice_with_apples_headers(monkeypatch):
    # Arrange
    sent = []
    monkeypatch.setattr(appstore_submit.urllib.request, "urlopen",
                        lambda req, timeout: sent.append((req.get_method(), req.full_url, req.data,
                                                          req.get_header("Content-type"))) or FakeResponse())
    ops = [{"method": "PUT", "url": "https://upload.example/1", "offset": 0, "length": 4,
            "requestHeaders": [{"name": "Content-Type", "value": "image/png"}]},
           {"method": "PUT", "url": "https://upload.example/2", "offset": 4, "length": 3, "requestHeaders": []}]

    # Act
    appstore_submit.upload_parts(ops, b"abcdefg")

    # Assert
    assert sent == [("PUT", "https://upload.example/1", b"abcd", "image/png"),
                    ("PUT", "https://upload.example/2", b"efg", None)]


def test_screens_refuses_to_run_without_three_to_ten_screenshots(monkeypatch, tmp_path):
    # Arrange : deux captures seulement
    for name in ("1.png", "2.png"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setattr(appstore_submit, "SCREENSHOTS_DIR", tmp_path)

    # Act / Assert : arrêt avant tout appel à Apple
    with pytest.raises(SystemExit, match="3 à 10 captures"):
        appstore_submit.screens("cle.p8", "1.0.0")


def test_the_store_screenshots_never_show_alcohol_casino_or_zicou():
    script = (ROOT / "ios/scripts/screenshots.sh").read_text()
    captures = [line for line in script.splitlines() if line.startswith("capture ") and "warmup" not in line]
    assert len(captures) >= 3
    assert not any(word in line for line in captures for word in ("drinks", "casino", "blackjack", "pet", "mood"))


def test_the_beta_app_is_never_picked_even_when_apple_lists_it_first():
    # Arrange : le filtre bundleId d'Apple renvoie aussi la BETA, parfois en premier
    apps = [{"id": "beta", "attributes": {"bundleId": "ch.bobycharbon.party.beta"}},
            {"id": "store", "attributes": {"bundleId": "ch.bobycharbon.party"}}]

    # Act / Assert
    assert appstore_submit.pick_app(apps) == "store"
    with pytest.raises(SystemExit):
        appstore_submit.pick_app(apps[:1])


class FakeAsc:
    """App Store Connect simulé : une fiche fr-FR avec un jeu 6,9", un jeu iPhone Duo (avec l'ancienne 09-musique),
    un jeu 6,5" et un aperçu vidéo ; note chaque appel."""

    def __init__(self):
        self.calls = []
        self.sets = {"s67": "APP_IPHONE_67", "sduo": "APP_IPHONE_DUO", "s65": "APP_IPHONE_65"}
        self.shots = {"s67": [("o1", "01-evenements.png")], "sduo": [("o2", "09-musique.png")], "s65": [("o3", "old.png")]}
        self.previews = {"p1": [("v1", "01-tour-de-l-app-886x1920.mp4")]}
        self.new = 0

    def __call__(self, key, method, path, body=None):
        self.calls.append((method, path))
        if path.startswith("/v1/apps?filter[bundleId]"):
            return {"data": [{"id": "app", "attributes": {"bundleId": "ch.bobycharbon.party"}}]}
        if path.startswith("/v1/apps/app/appStoreVersions"):
            return {"data": [{"id": "ver", "attributes": {"versionString": "1.0.0", "appVersionState": "PREPARE_FOR_SUBMISSION"}}]}
        if path == "/v1/appStoreVersions/ver/appStoreVersionLocalizations":
            return {"data": [{"id": "loc", "attributes": {"locale": "fr-FR"}}]}
        if path == "/v1/appStoreVersionLocalizations/loc/appScreenshotSets":
            return {"data": [{"id": i, "attributes": {"screenshotDisplayType": t}} for i, t in self.sets.items()]}
        if path.startswith("/v1/appScreenshotSets/") and path.endswith("/appScreenshots"):
            set_id = path.split("/")[3]
            return {"data": [{"id": i, "attributes": {"fileName": n}} for i, n in self.shots.get(set_id, [])]}
        if path == "/v1/appStoreVersionLocalizations/loc/appPreviewSets":
            return {"data": [{"id": "p1", "attributes": {"previewType": "IPHONE_67"}}]}
        if path == "/v1/appPreviewSets/p1/appPreviews":
            return {"data": [{"id": i, "attributes": {"fileName": n}} for i, n in self.previews["p1"]]}
        if method == "POST" and path == "/v1/appScreenshots":
            self.new += 1
            set_id = body["data"]["relationships"]["appScreenshotSet"]["data"]["id"]
            self.shots.setdefault(set_id + "-new", []).append((f"n{self.new}", body["data"]["attributes"]["fileName"]))
            return {"data": {"id": f"n{self.new}", "attributes": {"uploadOperations": []}}}
        if method == "GET" and path.startswith("/v1/appScreenshots/"):
            return {"data": {"attributes": {"assetDeliveryState": {"state": "COMPLETE"}}}}
        if path == "/v1/apps/app/appInfos":
            return {"data": []}
        if "appAvailabilityV2" in path or "appPriceSchedule" in path:
            return {"error": 404, "detail": ""}
        return {"data": {"id": "x", "attributes": {}}}


def test_screens_replaces_the_69_and_duo_sets_and_removes_old_sizes_and_previews(monkeypatch, tmp_path):
    # Arrange : 10 captures 6,9" et 10 captures Duo, App Store Connect simulé
    big, duo = tmp_path / "big", tmp_path / "duo"
    for folder in (big, duo):
        folder.mkdir()
        for i in range(1, 11):
            (folder / f"{i:02d}-ecran.png").write_bytes(b"png")
    fake = FakeAsc()
    monkeypatch.setattr(appstore_submit, "api", fake)
    monkeypatch.setattr(appstore_submit, "SCREENSHOTS_DIR", big)
    monkeypatch.setattr(appstore_submit, "DUO_SCREENSHOTS_DIR", duo)

    # Act
    appstore_submit.screens("cle.p8", "1.0.0")

    # Assert : anciennes captures (dont 09-musique du jeu Duo) retirées AVANT l'envoi, 10 + 10 envoyées, aperçu retiré
    deletes = [p for m, p in fake.calls if m == "DELETE"]
    assert deletes == ["/v1/appScreenshots/o1", "/v1/appScreenshots/o2", "/v1/appScreenshots/o3", "/v1/appPreviews/v1"]
    assert len(fake.shots["s67-new"]) == 10 and len(fake.shots["sduo-new"]) == 10
    uploads = [i for i, c in enumerate(fake.calls) if c == ("POST", "/v1/appScreenshots")]
    assert fake.calls.index(("DELETE", "/v1/appScreenshots/o1")) < uploads[0]
    assert uploads[9] < fake.calls.index(("DELETE", "/v1/appScreenshots/o2")) < uploads[10]


def test_check_lists_the_app_previews_by_type(monkeypatch, capsys):
    # Arrange
    fake = FakeAsc()
    monkeypatch.setattr(appstore_submit, "api", fake)

    # Act
    appstore_submit.details(appstore_submit.Asc("cle.p8"), "app")

    # Assert
    out = capsys.readouterr().out
    assert "aperçus vidéo IPHONE_67 : 1" in out and "01-tour-de-l-app-886x1920.mp4" in out
    assert "captures APP_IPHONE_DUO : 1" in out


def test_the_committed_store_screenshots_are_exact_rgb_copies_without_the_music_tab_capture():
    from PIL import Image
    pairs = (("docs/app-store/visuels/captures-6.9", "ios/appstore/screenshots", (1320, 2868)),
             ("docs/app-store/visuels/captures-duo", "ios/appstore/screenshots-duo", (1398, 2034)))
    for docs, store, size in pairs:
        files = sorted(p.name for p in (ROOT / docs).glob("*.png"))
        assert files == sorted(p.name for p in (ROOT / store).glob("*.png")) and 3 <= len(files) <= 10
        assert not any("musique" in name for name in files)
        for name in files:
            assert (ROOT / docs / name).read_bytes() == (ROOT / store / name).read_bytes(), name
            img = Image.open(ROOT / store / name)
            assert img.size == size and img.mode == "RGB", (name, img.size, img.mode)
