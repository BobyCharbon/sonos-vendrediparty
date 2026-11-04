"""Toutes les icônes de Party depuis UN dessin maître : tools/icon/zicou-icon.svg (Zicou, calques « fond » et « zicou »).

Usage : .venv/bin/python tools/icon/make_icons.py   (Playwright + Chromium pour dessiner le SVG, Pillow pour les PNG)

Produit :
- iPhone : ios/Party/Assets.xcassets/AppIcon(-Beta).appiconset : 1024 clair (opaque, sans transparence pour l'App Store),
  sombre (fond transparent, iOS 18) et teinté (niveaux de gris, iOS 18). La BETA porte une pastille « β ».
- Apple TV : ios/PartyTV/Assets.xcassets/App Icon & Top Shelf Image(-Beta).brandassets : calque arrière (fond, opaque),
  calque avant (Zicou, transparent ; pastille « β » pour la BETA), images du haut de l'écran d'accueil (Top Shelf).
- Web : app/static/apple-touch-icon.png, icon-192.png, icon-512.png, icon-maskable-512.png, favicon-32.png
  (+ web/events/assets/favicon.png) ; billets Wallet : app/wallet_assets/icon*.png, logo*.png.
"""

import io
import re
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
MASTER = Path(__file__).resolve().parent / "zicou-icon.svg"
IOS = ROOT / "ios" / "Party" / "Assets.xcassets"
TV = ROOT / "ios" / "PartyTV" / "Assets.xcassets"
STATIC = ROOT / "app" / "static"
WALLET = ROOT / "app" / "wallet_assets"
EVENTS_FAVICON = ROOT / "web" / "events" / "assets" / "favicon.png"

# Boîte occupée par Zicou dans le maître (antennes → bas de la boule, oreillettes comprises).
ZICOU_BOX = (120, 90, 904, 900)
MASKABLE_SCALE = 0.82      # zone sûre Android : tout Zicou dans le cercle central (80 %)
TV_FRONT_SIDE = 0.78       # Zicou occupe 78 % de la hauteur du calque avant
SHELF_SIDE = 0.8           # et 80 % de la hauteur des images Top Shelf
CORNER = 0.225             # arrondi des coins (favicon, logo Wallet)
BETA_BADGE = ('<g id="beta"><circle cx="{x}" cy="{y}" r="{r}" fill="#ffb547" stroke="#1b1030" stroke-width="{w}"/>'
              '<text x="{x}" y="{ty}" text-anchor="middle" font-family="-apple-system, system-ui, Helvetica, sans-serif" '
              'font-weight="900" font-size="{fs}" fill="#1b1030">β</text></g>')
TINT_FILTER = ('<filter id="gris"><feColorMatrix type="matrix" values="0.33 0.5 0.17 0 0.08  0.33 0.5 0.17 0 0.08  '
               '0.33 0.5 0.17 0 0.08  0 0 0 1 0"/></filter>')


def layers(svg: str) -> dict:
    """Découpe le maître en defs, fond et zicou (contenu des groupes du même id)."""
    defs = re.search(r'<defs>(.*?)</defs>', svg, re.S)
    out = {"defs": defs.group(1) if defs else ""}
    for name in ("fond", "zicou"):
        match = re.search(rf'<g id="{name}">(.*?)</g>\n', svg, re.S)
        if not match:
            raise SystemExit(f"Calque « {name} » introuvable dans {MASTER}")
        out[name] = match.group(1)
    return out


def badge(cx: float, cy: float, r: float) -> str:
    return BETA_BADGE.format(x=cx, y=cy, r=r, w=r * 0.11, ty=cy + r * 0.36, fs=r * 1.12)


def zicou_at(z: str, cx: float, cy: float, height: float) -> str:
    """Zicou centré en (cx, cy), haut de `height` pixels."""
    x0, y0, x1, y1 = ZICOU_BOX
    k = height / (y1 - y0)
    return f'<g transform="translate({cx} {cy}) scale({k:.4f}) translate({-(x0 + x1) / 2} {-(y0 + y1) / 2})">{z}</g>'


def svg_doc(w: int, h: int, body: str, defs: str, view: str = None) -> str:
    view = view or f"0 0 {w} {h}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="{w}" height="{h}">'
            f'<defs>{defs}{TINT_FILTER}</defs>{body}</svg>')


def fond_fill(fond: str, w: int, h: int) -> str:
    """Le fond carré du maître étiré sans déformation (rogné) sur w × h."""
    return f'<svg viewBox="0 0 1024 1024" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice">{fond}</svg>'


class Painter:
    """Dessine un SVG en PNG au pixel près avec Chromium (aucune dépendance native comme cairo)."""

    def __enter__(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.page = self.browser.new_page(device_scale_factor=1)
        return self

    def __exit__(self, *exc):
        self.browser.close()
        self.pw.stop()

    def png(self, svg: str, w: int, h: int, opaque: bool) -> Image.Image:
        self.page.set_viewport_size({"width": w, "height": h})
        self.page.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
        shot = self.page.screenshot(clip={"x": 0, "y": 0, "width": w, "height": h}, omit_background=True)
        image = Image.open(io.BytesIO(shot)).convert("RGBA")
        return image.convert("RGB") if opaque else image


def rounded(image: Image.Image) -> Image.Image:
    mask = Image.new("L", (image.width * 4, image.height * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.width - 1, mask.height - 1), radius=round(mask.width * CORNER), fill=255)
    out = image.convert("RGBA")
    out.putalpha(mask.resize(image.size, Image.LANCZOS))
    return out


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print("écrit", path.relative_to(ROOT), image.size, image.mode)


def icon_svgs(L: dict, beta: bool) -> dict:
    """Les trois apparences iOS 18 de l'icône 1024."""
    tag = badge(850, 850, 124) if beta else ""   # en bas à droite : loin des antennes
    return {
        "light": svg_doc(1024, 1024, L["fond"] + L["zicou"] + tag, L["defs"]),
        "dark": svg_doc(1024, 1024, L["zicou"] + tag, L["defs"]),
        "tinted": svg_doc(1024, 1024, f'<rect width="1024" height="1024" fill="#000"/><g filter="url(#gris)">{L["zicou"]}{tag}</g>', L["defs"]),
    }


def ios_icons(p: Painter, L: dict) -> None:
    for folder, beta in (("AppIcon.appiconset", False), ("AppIcon-Beta.appiconset", True)):
        svgs = icon_svgs(L, beta)
        save(p.png(svgs["light"], 1024, 1024, opaque=True), IOS / folder / "icon-1024.png")
        save(p.png(svgs["dark"], 1024, 1024, opaque=False), IOS / folder / "icon-1024-dark.png")
        save(p.png(svgs["tinted"], 1024, 1024, opaque=True).convert("L").convert("RGB"), IOS / folder / "icon-1024-tinted.png")
        (IOS / folder / "Contents.json").write_text(IOS_CONTENTS)


IOS_CONTENTS = """{
  "images" : [
    { "filename" : "icon-1024.png", "idiom" : "universal", "platform" : "ios", "size" : "1024x1024" },
    { "appearances" : [ { "appearance" : "luminosity", "value" : "dark" } ],
      "filename" : "icon-1024-dark.png", "idiom" : "universal", "platform" : "ios", "size" : "1024x1024" },
    { "appearances" : [ { "appearance" : "luminosity", "value" : "tinted" } ],
      "filename" : "icon-1024-tinted.png", "idiom" : "universal", "platform" : "ios", "size" : "1024x1024" }
  ],
  "info" : { "author" : "xcode", "version" : 1 }
}
"""


def tv_icons(p: Painter, L: dict) -> None:
    for folder, beta in (("App Icon & Top Shelf Image.brandassets", False), ("App Icon & Top Shelf Image Beta.brandassets", True)):
        base = TV / folder
        for png in sorted(base.glob("**/*.png")):
            w, h = Image.open(png).size
            rel = str(png.relative_to(base))
            if "Back.imagestacklayer" in rel:
                image = p.png(svg_doc(w, h, fond_fill(L["fond"], w, h), L["defs"]), w, h, opaque=True)
            elif "Front.imagestacklayer" in rel:
                side = h * TV_FRONT_SIDE
                tag = badge(w / 2 + side * 0.5, h / 2 + side * 0.36, side * 0.15) if beta else ""
                image = p.png(svg_doc(w, h, zicou_at(L["zicou"], w / 2, h / 2, side) + tag, L["defs"]), w, h, opaque=False)
            else:  # Top Shelf : fond + Zicou au centre, sans texte
                body = fond_fill(L["fond"], w, h) + zicou_at(L["zicou"], w / 2, h / 2, h * SHELF_SIDE)
                image = p.png(svg_doc(w, h, body, L["defs"]), w, h, opaque=True)
            save(image, png)


def web_icons(p: Painter, L: dict) -> None:
    light = icon_svgs(L, beta=False)["light"]
    big = p.png(light, 1024, 1024, opaque=True)
    for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
        save(p.png(light.replace('width="1024" height="1024"', f'width="{size}" height="{size}"', 1), size, size, opaque=True), STATIC / name)
    maskable = svg_doc(512, 512, fond_fill(L["fond"], 512, 512)
                       + zicou_at(L["zicou"], 256, 256, 512 * MASKABLE_SCALE * (ZICOU_BOX[3] - ZICOU_BOX[1]) / 1024), L["defs"])
    save(p.png(maskable, 512, 512, opaque=True), STATIC / "icon-maskable-512.png")
    favicon = rounded(big.resize((32, 32), Image.LANCZOS))
    save(favicon, STATIC / "favicon-32.png")
    save(favicon, EVENTS_FAVICON)
    for suffix, k in (("", 1), ("@2x", 2), ("@3x", 3)):
        save(big.resize((29 * k, 29 * k), Image.LANCZOS), WALLET / f"icon{suffix}.png")
        save(rounded(big.resize((50 * k, 50 * k), Image.LANCZOS)), WALLET / f"logo{suffix}.png")


def main() -> None:
    L = layers(MASTER.read_text())
    with Painter() as p:
        ios_icons(p, L)
        tv_icons(p, L)
        web_icons(p, L)


if __name__ == "__main__":
    main()
