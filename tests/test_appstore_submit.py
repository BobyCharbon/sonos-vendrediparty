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
