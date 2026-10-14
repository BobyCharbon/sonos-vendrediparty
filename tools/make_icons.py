"""Génère les icônes de l'app (écran d'accueil iOS, Android, favicon).

Usage : python tools/make_icons.py   (nécessite Pillow, uniquement pour régénérer les PNG)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "app" / "static"
S = 1024  # dessin en grand puis réduction, pour des bords lisses


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def draw() -> Image.Image:
    img = Image.new("RGB", (S, S))
    top_left, bottom_right = (255, 79, 154), (255, 179, 71)  # couleurs d'accent de l'app
    px = img.load()
    for y in range(S):
        for x in range(S):
            px[x, y] = lerp(top_left, bottom_right, (x + y) / (2 * S))

    # Halo sombre derrière les notes pour la profondeur.
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse((170, 170, 854, 854), fill=90)
    img.paste((20, 10, 30), mask=glow.filter(ImageFilter.GaussianBlur(120)))

    # Double croche (♫) dessinée à la main : deux têtes, deux hampes, une barre.
    d = ImageDraw.Draw(img)
    white = (255, 255, 255)
    dx, dy = 92, 36  # recentre le dessin
    heads = [(250 + dx, 640 + dy), (590 + dx, 580 + dy)]
    for cx, cy in heads:
        head = Image.new("L", (S, S), 0)
        ImageDraw.Draw(head).ellipse((cx - 115, cy - 82, cx + 115, cy + 82), fill=255)
        head = head.rotate(20, center=(cx, cy))
        img.paste(white, mask=head)
    stem_w = 46
    for (cx, cy), top in zip(heads, (300 + dy, 240 + dy)):
        x = cx + 115 - stem_w
        d.rectangle((x - 6, top, x + stem_w - 6, cy - 10), fill=white)
    d.polygon([(355 + dx, 300 + dy), (699 + dx, 240 + dy), (699 + dx, 340 + dy), (355 + dx, 400 + dy)], fill=white)
    return img


def main():
    big = draw()
    for name, size in [("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512), ("favicon-32.png", 32)]:
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print("écrit", OUT / name)


if __name__ == "__main__":
    main()
