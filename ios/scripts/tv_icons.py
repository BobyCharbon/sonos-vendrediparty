#!/usr/bin/env python3
"""Icônes Apple TV de la production (sans bandeau BETA) à partir de celles de la BETA et de l'icône iPhone de production.

Les deux jeux gardent le même fond et le même placement ; seule l'icône change :
  python3 ios/scripts/tv_icons.py
"""
import glob
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "PartyTV" / "Assets.xcassets"
BETA = ASSETS / "App Icon & Top Shelf Image Beta.brandassets"
PROD = ASSETS / "App Icon & Top Shelf Image.brandassets"
ICON = Image.open(ROOT / "Party" / "Assets.xcassets" / "AppIcon.appiconset" / "icon-1024.png").convert("RGB")
FRONT_SIDE = 0.78  # icône du calque avant : 78 % de la hauteur, centrée
SHELF_SIDE, SHELF_TOP = 0.6, 0.2  # image du haut de l'écran d'accueil : 60 % de la hauteur, à 20 % du haut


def rounded_mask(side: int) -> Image.Image:
    """Coins arrondis repris de l'icône BETA (calque avant le plus grand), mis à la taille voulue."""
    front = Image.open(next(BETA.glob("App Icon - App Store.imagestack/Front*/Content.imageset/*.png"))).convert("RGBA")
    alpha = front.getchannel("A")
    return alpha.crop(alpha.getbbox()).resize((side, side), Image.LANCZOS)


def place(canvas: Image.Image, side: int, top: int) -> Image.Image:
    left = (canvas.width - side) // 2
    canvas.paste(ICON.resize((side, side), Image.LANCZOS), (left, top), rounded_mask(side))
    return canvas


def main() -> None:
    for beta in sorted(glob.glob(str(BETA / "**" / "*.png"), recursive=True)):
        rel = Path(beta).relative_to(BETA)
        out = PROD / rel
        image = Image.open(beta)
        if "Front.imagestacklayer" in str(rel):
            side = round(image.height * FRONT_SIDE)
            image = place(Image.new("RGBA", image.size, (0, 0, 0, 0)), side, (image.height - side) // 2)
        elif "Top Shelf" in str(rel):
            image = place(image.convert("RGB"), round(image.height * SHELF_SIDE), round(image.height * SHELF_TOP))
        image.save(out)  # le fond (calque arrière) reste identique
        print(rel)


if __name__ == "__main__":
    main()
