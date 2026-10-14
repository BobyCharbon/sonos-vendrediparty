"""Génère les icônes de l'app (écran d'accueil iOS, Android, favicon) depuis tools/icon-source.png.

Usage : python tools/make_icons.py   (nécessite Pillow, uniquement pour régénérer les PNG)
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "app" / "static"
# Image « Party ! » déjà cadrée : pas de recadrage.
CROP = 0


def main():
    src = Image.open(HERE / "icon-source.png").convert("RGB")
    w, h = src.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    m = round(side * CROP)
    square = src.crop((left + m, top + m, left + side - m, top + side - m))
    for name, size in [("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512), ("favicon-32.png", 32)]:
        square.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print("écrit", OUT / name)


if __name__ == "__main__":
    main()
