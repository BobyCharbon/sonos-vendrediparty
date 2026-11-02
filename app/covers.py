"""Couvertures des événements créés par l'assistant IA : toujours une image, gardée chez nous.

1. l'image de la page partagée (og:image, flyer), téléchargée ;
2. sinon une capture d'écran jointe par la personne (souvent le flyer lui-même) ;
3. sinon une affiche générée : titre, date et lieu sur un dégradé aux couleurs de Party.

Toute image est réouverte et réenregistrée en JPEG (1600 px au plus) : rien d'autre qu'une image propre n'est servi.
Fichiers dans DATA_DIR/covers, nommés par leur empreinte, servis sur /covers/<empreinte>.jpg."""
import datetime
import hashlib
import io
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT = Path(__file__).parent / "fonts" / "BricolageGrotesque.ttf"
MAX_SIDE = 1600
MAX_PIXELS = 25_000_000  # au-delà, le décodage coûte trop de mémoire et de temps (5000 × 5000)
POSTER = (1600, 900)
NAME = re.compile(r"^[0-9a-f]{24}p?\.jpg$")  # « p » : affiche générée (refaite si le titre ou la date change)
# Dégradés nocturnes de Party (fond, milieu, éclat) : choisis selon le titre, la même affiche à chaque fois.
PALETTES = [((21, 16, 42), (90, 24, 120), (255, 79, 154)), ((10, 18, 40), (34, 60, 140), (127, 214, 232)),
            ((26, 12, 30), (140, 30, 70), (255, 179, 71)), ((12, 26, 28), (20, 100, 90), (91, 227, 166)),
            ((20, 10, 40), (70, 40, 160), (185, 167, 255))]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
          "décembre"]
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class CoverError(ValueError):
    """Image illisible ou refusée."""


class Covers:
    def __init__(self, data_dir: Path, public_url: str):
        self.dir = Path(data_dir) / "covers"
        self.public_url = public_url.rstrip("/")

    def path(self, name: str) -> Path | None:
        return self.dir / name if NAME.match(name) and (self.dir / name).is_file() else None

    def owns(self, url: str) -> bool:
        """Une couverture servie par nous (jamais une image externe choisie par l'app)."""
        prefix = f"{self.public_url}/covers/"
        return bool(url) and url.startswith(prefix) and bool(NAME.match(url[len(prefix):]))

    @staticmethod
    def is_poster(url: str) -> bool:
        return bool(re.search(r"/covers/[0-9a-f]{24}p\.jpg$", url or ""))

    def _store(self, image: Image.Image, poster: bool = False) -> str:
        out = io.BytesIO()
        image.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
        data = out.getvalue()
        name = hashlib.sha256(data).hexdigest()[:24] + ("p" if poster else "") + ".jpg"
        self.dir.mkdir(parents=True, exist_ok=True)
        target = self.dir / name
        if not target.exists():
            target.write_bytes(data)
        return f"{self.public_url}/covers/{name}"

    def keep(self, data: bytes) -> str:
        """Une image reçue (page, capture) → réencodée, réduite, gardée ; son adresse publique."""
        try:
            with Image.open(io.BytesIO(data)) as raw:
                if raw.width * raw.height > MAX_PIXELS:
                    raise CoverError("image trop grande")
                image = ImageOps.exif_transpose(raw).convert("RGB")
        except CoverError:
            raise
        except Exception as e:  # noqa: BLE001 — Pillow lève aussi SyntaxError, struct.error… : toute image cassée est refusée
            raise CoverError("image illisible") from e
        if min(image.size) < 120:
            raise CoverError("image trop petite (icône)")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        return self._store(image)

    def poster(self, title: str, when: str = "", place: str = "") -> str:
        """Affiche générée : le titre en grand, la date et le lieu, sur un dégradé de la soirée."""
        return self._store(render_poster(title, when, place), poster=True)


def _font(size: int, weight: str = "ExtraBold") -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT), size)
    try:
        font.set_variation_by_name(weight)
    except (OSError, ValueError):
        pass  # FreeType sans variations : graisse par défaut
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, lines: int) -> list[str]:
    """Coupe le texte en lignes de `width` px au plus ; au-delà de `lines` lignes, la dernière finit par « … »."""
    words, out, line = text.split(), [], ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width or not line:
            line = test
            continue
        out.append(line)
        line = word
    if line:
        out.append(line)
    if len(out) > lines:
        out = out[:lines]
        last = out[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        out[-1] = last.rstrip() + "…"
    return out


def _background(seed: int) -> tuple[Image.Image, tuple[int, int, int]]:
    rng = random.Random(seed)
    base, mid, glow = PALETTES[seed % len(PALETTES)]
    w, h = POSTER
    # Dégradé diagonal (mélange d'un dégradé horizontal et d'un vertical, sans coins durs), puis halos flous : une
    # ambiance de boîte, sans aucune image extérieure.
    ramp = Image.linear_gradient("L")
    mask = Image.blend(ramp.rotate(90).resize((w, h)), ramp.resize((w, h)), 0.4)
    image = Image.composite(Image.new("RGB", (w, h), mid), Image.new("RGB", (w, h), base), mask)
    halo = Image.new("RGB", (w, h), (0, 0, 0))
    hd = ImageDraw.Draw(halo)
    for _ in range(5):
        r = rng.randint(140, 360)
        cx, cy = rng.randint(w // 2, w), rng.randint(-100, h)
        hd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(int(c * rng.uniform(0.35, 0.8)) for c in glow))
    halo = halo.filter(ImageFilter.GaussianBlur(90))
    return Image.composite(halo, image, halo.convert("L")), glow


def render_poster(title: str, when: str = "", place: str = "") -> Image.Image:
    title = " ".join((title or "Soirée").split())[:120]
    image, glow = _background(int(hashlib.sha256(title.encode()).hexdigest(), 16))
    w, h = POSTER
    draw = ImageDraw.Draw(image)
    left, width = 110, w - 220
    size = 150
    while True:  # titre sur 3 lignes au plus, aussi grand que possible
        font = _font(size)
        lines = _wrap(draw, title, font, width, 3)
        if size <= 70 or (not lines[-1].endswith("…") and all(draw.textlength(x, font=font) <= width for x in lines)):
            break
        size -= 8
    step = int(size * 1.05)
    y = max(110, (h - len(lines) * step) // 2 - 70)
    for line in lines:
        draw.text((left, y), line, font=font, fill=(255, 255, 255))
        y += step
    y += 24
    small = _font(48, "SemiBold")
    for info, color in ((when, glow), (place, (230, 224, 250))):
        if info:
            draw.text((left, y), _wrap(draw, info, small, width, 1)[0], font=small, fill=color)
            y += 66
    draw.text((left, h - 110), "Party", font=_font(42, "Bold"), fill=glow)
    return image


def when_text(start: str, end: str = "") -> str:
    """« 2026-11-20T22:00 » → « vendredi 20 novembre · 22:00 – 06:00 » (heure de Suisse, comme dans le brouillon)."""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d:\d\d)", start or "")
    if not m:
        return ""
    day = datetime.date(int(m[1]), int(m[2]), int(m[3]))
    text = f"{DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} · {m[4]}"
    e = re.match(r"\d{4}-\d\d-\d\dT(\d\d:\d\d)", end or "")
    return text + (f" – {e[1]}" if e else "")
