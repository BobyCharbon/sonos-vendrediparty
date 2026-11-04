"""Icônes « Zicou » : générées depuis tools/icon/zicou-icon.svg, aux bonnes tailles, sans transparence là où Apple
l'interdit (icône App Store 1024, calques arrière Apple TV, Top Shelf), variantes iOS 18 déclarées, BETA distincte,
PWA avec icône maskable et liens rafraîchis."""
import json
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "ios" / "Party" / "Assets.xcassets"
TV = ROOT / "ios" / "PartyTV" / "Assets.xcassets"
STATIC = ROOT / "app" / "static"


def has_alpha(path: Path) -> bool:
    image = Image.open(path)
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def test_the_master_drawing_has_its_two_named_layers():
    svg = (ROOT / "tools" / "icon" / "zicou-icon.svg").read_text()
    assert '<g id="fond">' in svg and '<g id="zicou">' in svg and 'viewBox="0 0 1024 1024"' in svg
    assert "<text" not in svg   # icône sans texte


@pytest.mark.parametrize("folder", ["AppIcon.appiconset", "AppIcon-Beta.appiconset"])
def test_iphone_icon_is_opaque_and_declares_dark_and_tinted(folder):
    contents = json.loads((IOS / folder / "Contents.json").read_text())
    by_look = {(img.get("appearances") or [{}])[0].get("value", "any"): img["filename"] for img in contents["images"]}
    assert set(by_look) == {"any", "dark", "tinted"}
    for look, name in by_look.items():
        assert Image.open(IOS / folder / name).size == (1024, 1024)
    assert not has_alpha(IOS / folder / by_look["any"])        # App Store : aucune transparence
    assert not has_alpha(IOS / folder / by_look["tinted"])


def test_the_beta_icon_stays_visibly_different():
    prod = Image.open(IOS / "AppIcon.appiconset" / "icon-1024.png").convert("RGB")
    beta = Image.open(IOS / "AppIcon-Beta.appiconset" / "icon-1024.png").convert("RGB")
    corner = (900, 900)   # pastille « β » ambre (hors du glyphe)
    assert prod.getpixel(corner) != beta.getpixel(corner)
    assert beta.getpixel(corner)[0] > 200 and beta.getpixel(corner)[2] < 120


def test_apple_tv_layers_back_and_shelf_are_opaque_front_is_transparent():
    pngs = sorted(TV.glob("*.brandassets/**/*.png"))
    assert len(pngs) == 20
    for png in pngs:
        assert has_alpha(png) == ("Front.imagestacklayer" in str(png)), png


def test_web_icons_sizes_and_maskable_manifest():
    for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512),
                       ("icon-maskable-512.png", 512), ("favicon-32.png", 32)):
        assert Image.open(STATIC / name).size == (size, size), name
    for manifest in ("manifest.json", "manifest-admin.json"):
        icons = json.loads((STATIC / manifest).read_text())["icons"]
        assert {"any", "maskable"} == {i["purpose"] for i in icons}
        assert all((STATIC / i["src"].split("?")[0].removeprefix("/static/")).exists() for i in icons)
    for page in ("index.html", "admin.html"):
        html = (STATIC / page).read_text()
        assert "apple-touch-icon.png?v=3" in html and "favicon-32.png?v=3" in html
