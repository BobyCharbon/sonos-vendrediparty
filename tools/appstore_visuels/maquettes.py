"""Maquettes marketing de la fiche App Store et bannières de Vendredi Party (HTML rendu par Playwright / Chromium).

    .venv/bin/python tools/appstore_visuels/maquettes.py <captures brutes 6,9"> [<captures brutes iPhone Duo>]

Entrée : captures brutes du simulateur 6,9" (1320 × 2868, barre d'état 9:41), faites par
ios/PartyUITests/VisuelsAppStoreUITests.swift (voir docs/app-store/visuels/README.md).
Sortie (docs/app-store/visuels/ ; VISUELS_ESSAI=<dossier> pour un essai) :
- captures-6.9/NN-nom.png : 1320 × 2868, PNG sans transparence (type APP_IPHONE_67) ; recopiées dans ios/appstore/screenshots/
  (c'est là que tools/appstore_submit.py screens les prend, dans l'ordre des noms) ;
- captures-duo/NN-nom.png : taille de l'écran du simulateur iPhone Duo, recopiées dans ios/appstore/screenshots-duo/ ;
- bannieres/ : en-tête 1920 × 1080, partage Open Graph 1200 × 630, carré 1080 × 1080.
L'icône de l'app (ios/Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png) est reprise telle quelle, jamais modifiée.
"""
import base64
import shutil
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / "app/fonts/BricolageGrotesque.ttf"
ICON = ROOT / "ios/Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png"
NAME = "Vendredi Party"
TAGLINE = "Musique, jeux et soirées"

# (fichier de sortie, capture brute, titre (« *mot* » = en couleur), sous-titre, couleur d'ambiance)
SHOTS = [  # ordre d'affichage sur l'App Store (les 3 premières : résultats de recherche)
    ("01-evenements", "brut-evenements", "Toute la soirée *sur ton téléphone*", "Tes événements, tes groupes et tes invitations", "#FF4F9A"),
    ("02-fiche", "brut-fiche", "Une fiche claire, *tout est dedans*", "Qui vient, la date, le lieu et l’itinéraire", "#B9A7FF"),
    ("03-jeux", "brut-jeux", "Une salle de jeux *pour tout le groupe*", "Un code, tout le monde rejoint et on vote", "#FFB347"),
    ("04-discussion-evenement", "brut-discussion-evenement", "Discute avec *ceux qui viennent*", "La discussion de la soirée, entre invités", "#6CC7FF"),
    ("05-ia", "brut-ia", "Décris ta soirée, *l’IA prépare tout*", "Tu vérifies, tu invites et tu publies", "#B9A7FF"),
    ("06-sondage", "brut-sondage-2", "Fixe la date *avec ta bande*", "Chacun vote : oui, si besoin ou non", "#5BE3A6"),
    ("07-billet", "brut-billet", "Ton billet *dans ta poche*", "Un QR scanné à l’entrée par l’organisateur", "#FF4F9A"),
    ("08-discussions", "brut-discussions", "Groupes, messages *et soirées*", "Toutes tes conversations au même endroit", "#B9A7FF"),
    ("09-musique", "brut-musique", "La musique de la soirée, *ensemble*", "Chacun propose ses titres, ils rejoignent la file", "#6CC7FF"),
    ("10-pot-commun", "brut-pot", "Les comptes *sans prise de tête*", "Pot commun : qui a payé quoi, qui doit combien", "#FFB347"),
]


def data_url(path: Path) -> str:
    kind = "image/png" if path.suffix == ".png" else "image/jpeg"
    return f"data:{kind};base64," + base64.b64encode(path.read_bytes()).decode()


def rich(title: str) -> str:
    parts = title.split("*")
    return "".join(f'<span class="hi">{p}</span>' if i % 2 else p for i, p in enumerate(parts))


BASE_CSS = """
@font-face{font-family:Bricolage;src:url('%(font)s') format('truetype');font-weight:200 800}
*{box-sizing:border-box}
html,body{margin:0;width:%(w)dpx;height:%(h)dpx;overflow:hidden;background:#120C26}
body{font-family:Bricolage,-apple-system,sans-serif;color:#fff;position:relative}
.sky{position:absolute;inset:0;background:
  radial-gradient(60%% 38%% at 15%% 8%%,%(accent)s66,transparent 70%%),
  radial-gradient(55%% 35%% at 95%% 30%%,#6CC7FF44,transparent 70%%),
  radial-gradient(70%% 40%% at 50%% 105%%,#FF4F9A55,transparent 70%%),
  linear-gradient(180deg,#1B1038 0%%,#120C26 55%%,#0B0817 100%%)}
.grid{position:absolute;left:-20%%;right:-20%%;bottom:-4%%;height:30%%;transform:perspective(700px) rotateX(62deg);
  background-image:linear-gradient(#ffffff1c 2px,transparent 2px),linear-gradient(90deg,#ffffff1c 2px,transparent 2px);
  background-size:110px 110px;-webkit-mask-image:linear-gradient(0deg,#000 30%%,transparent)}
.star{position:absolute;width:10px;height:10px;border-radius:50%%;background:#fff;box-shadow:0 0 18px 6px #ffffff88}
.hi{background:linear-gradient(90deg,#FF8FC0,#FFB347);-webkit-background-clip:text;background-clip:text;color:transparent}
"""

SHOT_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>%(css)s
.title{position:absolute;left:90px;right:90px;top:150px;text-align:center;font-weight:800;font-size:116px;line-height:1.02;
  letter-spacing:-0.5px;text-wrap:balance}
.sub{position:absolute;left:110px;right:110px;top:%(subtop)dpx;text-align:center;font-weight:500;font-size:50px;line-height:1.2;
  color:#D9D0FF;text-wrap:balance}
.phone{position:absolute;left:50%%;top:%(phonetop)dpx;width:%(pw)dpx;height:%(ph)dpx;transform:translateX(-50%%);
  border-radius:%(pr)dpx;padding:%(bz)dpx;background:linear-gradient(145deg,#3A3358,#15102A 45%%,#2A2346);
  box-shadow:0 0 0 3px #ffffff22,0 60px 140px -20px #000c,0 0 120px -10px %(accent)s77}
.screen{width:100%%;height:100%%;border-radius:%(sr)dpx;background:url('%(shot)s') center/cover;overflow:hidden}
</style></head><body><div class="sky"></div><div class="grid"></div>%(stars)s
<div class="title">%(title)s</div><div class="sub">%(sub)s</div>
<div class="phone"><div class="screen"></div></div></body></html>"""

STARS = "".join(f'<div class="star" style="left:{x}%;top:{y}%;transform:scale({s})"></div>'
                for x, y, s in [(8, 4, .6), (91, 6, .9), (4, 22, .5), (96, 18, .5), (12, 40, .4), (90, 46, .6)])

BANNER_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>%(css)s
.wrap{position:absolute;inset:0;display:flex;align-items:center;gap:%(gap)dpx;padding:0 %(pad)dpx;flex-direction:%(dir)s;
  justify-content:center;text-align:%(align)s}
.icon{width:%(icon)dpx;height:%(icon)dpx;border-radius:%(ir)dpx;background:url('%(iconurl)s') center/cover;flex:none;
  box-shadow:0 0 0 3px #ffffff26,0 30px 90px -10px #FF4F9Aaa,0 0 160px -20px #6CC7FF99}
.name{font-weight:800;font-size:%(fs)dpx;line-height:1;letter-spacing:-0.5px;white-space:nowrap}
.tag{margin-top:%(tgap)dpx;font-weight:500;font-size:%(ts)dpx;color:#D9D0FF}
.chips{margin-top:%(cgap)dpx;display:flex;gap:16px;justify-content:%(cj)s}
.chip{font-size:%(cs)dpx;font-weight:600;padding:.35em .8em;border-radius:999px;background:#ffffff14;border:2px solid #ffffff26}
</style></head><body><div class="sky"></div><div class="grid"></div>%(stars)s
<div class="wrap"><div class="icon"></div><div><div class="name">Vendredi <span class="hi">Party</span></div>
<div class="tag">%(tagline)s</div>
<div class="chips"><span class="chip">🎉 Soirées</span><span class="chip">🎲 Jeux</span><span class="chip">🎤 Musique</span></div>
</div></div></body></html>"""

BANNERS = [  # nom, largeur, hauteur, disposition
    ("en-tete-1920x1080", 1920, 1080, dict(dir="row", align="left", gap=90, pad=150, icon=440, ir=98, fs=150, ts=64, tgap=26,
                                            cgap=44, cs=40, cj="flex-start")),
    ("partage-1200x630", 1200, 630, dict(dir="row", align="left", gap=60, pad=80, icon=290, ir=64, fs=94, ts=42, tgap=16,
                                          cgap=28, cs=27, cj="flex-start")),
    ("carre-1080x1080", 1080, 1080, dict(dir="column", align="center", gap=56, pad=60, icon=420, ir=94, fs=116, ts=52, tgap=22,
                                          cgap=40, cs=36, cj="center")),
]


def flatten(path: Path):
    """PNG RVB sans canal alpha (exigé par Apple pour les captures)."""
    Image.open(path).convert("RGB").save(path, optimize=True)


def shots(pg, raw: Path, caps: Path, font: str, size: tuple[int, int]):
    """Une maquette par capture brute, à la taille exacte `size` (pixels). Mise en page dessinée sur 1320 px de large,
    agrandie ou réduite ensuite (même rendu pour l'iPhone 6,9" et pour l'iPhone Duo)."""
    w, h = size
    dh = round(1320 * h / w)
    pg.set_viewport_size({"width": 1320, "height": dh})
    caps.mkdir(parents=True, exist_ok=True)
    for name, src, title, sub, accent in SHOTS:
        shot = raw / f"{src}.png"
        if not shot.exists():
            print("absente :", shot)
            continue
        sw, sh = Image.open(shot).size
        lines = 2 if len(title.replace("*", "")) > 17 else 1
        subtop = 150 + lines * 118 + 40
        top = subtop + 190
        bz = 22
        # Le téléphone tient en entier sous le titre (écran étroit du 6,9" comme écran plus large de l'iPhone Duo).
        pw = min(1040, round((dh - top - 60 - 2 * bz) * sw / sh) + 2 * bz)
        ph = round((pw - 2 * bz) * sh / sw) + 2 * bz
        css = BASE_CSS % {"font": font, "w": 1320, "h": dh, "accent": accent}
        pg.set_content(SHOT_HTML % {"css": css, "title": rich(title), "sub": sub, "shot": data_url(shot), "stars": STARS,
                                    "subtop": subtop, "phonetop": top, "pw": pw, "ph": ph, "pr": round(pw * 0.144), "bz": bz,
                                    "sr": round(pw * 0.123), "accent": accent})
        pg.wait_for_timeout(250)
        target = caps / f"{name}.png"
        pg.screenshot(path=str(target))
        img = Image.open(target).convert("RGB")
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS)
        img.save(target, optimize=True)  # PNG RVB, sans canal alpha (exigé par Apple)
        print(target, img.size)


def render(raw: Path, out: Path, store: Path | None, raw_duo: Path | None = None, store_duo: Path | None = None):
    ban = out / "bannieres"
    ban.mkdir(parents=True, exist_ok=True)
    # Police de Party (Bricolage Grotesque, licence OFL) en data URL : une page set_content ne lit pas de fichier local.
    font = "data:font/ttf;base64," + base64.b64encode(FONT.read_bytes()).decode()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1320, "height": 2868})
        shots(pg, raw, out / "captures-6.9", font, (1320, 2868))
        if raw_duo and raw_duo.exists():
            duo = Image.open(next(raw_duo.glob("brut-*.png"))).size  # taille de l'écran du simulateur iPhone Duo
            shots(pg, raw_duo, out / "captures-duo", font, duo)
        for name, w, h, lay in BANNERS:
            pg.set_viewport_size({"width": w, "height": h})
            css = BASE_CSS % {"font": font, "w": w, "h": h, "accent": "#FF4F9A"}
            pg.set_content(BANNER_HTML % {"css": css, "iconurl": data_url(ICON), "tagline": TAGLINE, "stars": STARS, **lay})
            pg.wait_for_timeout(250)
            target = ban / f"{name}.png"
            pg.screenshot(path=str(target))
            flatten(target)
            print(target)
        b.close()
    for caps, dest in ((out / "captures-6.9", store), (out / "captures-duo", store_duo)):
        if dest is None or not caps.exists():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        for old in dest.glob("*.png"):
            old.unlink()
        for f in sorted(caps.glob("*.png")):
            shutil.copy(f, dest / f.name)


if __name__ == "__main__":
    # maquettes.py <brut 6,9"> [<brut iPhone Duo>] : sortie dans docs/app-store/visuels/ et ios/appstore/screenshots(-duo)/.
    # Avec VISUELS_ESSAI=<dossier> : essai dans ce dossier, sans toucher au projet.
    import os
    essai = os.environ.get("VISUELS_ESSAI")
    out = Path(essai) if essai else ROOT / "docs/app-store/visuels"
    render(Path(sys.argv[1]), out, None if essai else ROOT / "ios/appstore/screenshots",
           Path(sys.argv[2]) if len(sys.argv) > 2 else None, None if essai else ROOT / "ios/appstore/screenshots-duo")
