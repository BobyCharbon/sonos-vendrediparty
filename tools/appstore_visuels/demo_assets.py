"""Images des données de démonstration des captures App Store : photos de profil (emoji sur dégradé, jamais un visage)
et couvertures d'événements (scènes dessinées en CSS + emoji). Tout est fabriqué ici : aucune photo de banque d'images.

    .venv/bin/python tools/appstore_visuels/demo_assets.py <dossier de sortie>
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Prénom → (emoji, couleur 1, couleur 2). Les mêmes noms que demo_data.PEOPLE.
AVATARS = {
    "lea": ("🌸", "#FF8FC0", "#7B6CF6"), "hugo": ("🎧", "#6CC7FF", "#3D3DBF"), "ines": ("🦋", "#B9A7FF", "#FF4F9A"),
    "tom": ("🛹", "#FFB347", "#FF4F9A"), "zoe": ("🪩", "#FF4F9A", "#6B2BD9"), "nathan": ("⚡", "#FFE27A", "#FF7A59"),
    "camille": ("🌻", "#FFE27A", "#22B07D"), "yanis": ("🎸", "#5BE3A6", "#1D5FBF"), "chloe": ("🌈", "#8FD6FF", "#B9A7FF"),
    "malik": ("🏀", "#FF7A59", "#7B2CBF"), "sarah": ("🌙", "#CBBDFF", "#2A2470"), "jules": ("🦊", "#FFC977", "#C2185B"),
}

# Couvertures : fond (dégradé), emoji principal, emoji de décor.
COVERS = {
    "disco": ("radial-gradient(80% 70% at 50% 30%, #FF4F9A 0%, #7B2CBF 45%, #15102A 100%)", "🪩", ["✨", "🎂", "🎈", "✨", "🎶", "🎈"]),
    "raclette": ("radial-gradient(90% 80% at 40% 30%, #FFC977 0%, #FF7A59 40%, #3B1A12 100%)", "🧀", ["🥔", "🔥", "🥔", "🫕", "✨"]),
    "karaoke": ("radial-gradient(80% 70% at 60% 30%, #6CC7FF 0%, #3D3DBF 45%, #0B0817 100%)", "🎤", ["🎶", "✨", "🎵", "🎶", "⭐"]),
    "chalet": ("linear-gradient(180deg, #8FD6FF 0%, #3D8BFF 45%, #1B1650 100%)", "🏔️", ["❄️", "🎿", "❄️", "☃️", "❄️"]),
    "jeux": ("radial-gradient(80% 70% at 40% 30%, #7CEDBB 0%, #22B07D 40%, #0F2A22 100%)", "🎲", ["♟️", "🃏", "🧩", "🎯", "✨"]),
    "coloc": ("radial-gradient(90% 80% at 40% 25%, #7CEDBB 0%, #22B07D 45%, #0F2A22 100%)", "🛋️", ["🪴", "🍕", "🎮", "🪴", "💡"]),
    "pique-nique": ("radial-gradient(90% 80% at 50% 20%, #FFEA9C 0%, #FFB347 40%, #2E6B3A 100%)", "🧺", ["🌳", "🍉", "☀️", "🥗", "🌼"]),
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;width:%(w)dpx;height:%(h)dpx;overflow:hidden}
.bg{position:absolute;inset:0;background:%(bg)s}
.glow{position:absolute;inset:0;background:radial-gradient(60%% 50%% at 50%% 55%%,rgba(255,255,255,.22),transparent 70%%)}
.grid{position:absolute;left:-10%%;right:-10%%;bottom:-5%%;height:38%%;transform:perspective(500px) rotateX(60deg);
 background-image:linear-gradient(rgba(255,255,255,.18) 2px,transparent 2px),linear-gradient(90deg,rgba(255,255,255,.18) 2px,transparent 2px);
 background-size:80px 80px;opacity:%(grid)s}
.main{position:absolute;left:50%%;top:%(top)s;transform:translate(-50%%,-50%%);font-size:%(size)dpx;line-height:1;
 filter:drop-shadow(0 18px 40px rgba(0,0,0,.45))}
.d{position:absolute;font-size:%(dsize)dpx;line-height:1;filter:drop-shadow(0 8px 18px rgba(0,0,0,.35))}
</style></head><body><div class="bg"></div><div class="glow"></div><div class="grid"></div>%(deco)s
<div class="main">%(main)s</div></body></html>"""

SPOTS = [(14, 22, -12), (80, 18, 10), (22, 70, 8), (84, 68, -8), (50, 12, 0), (64, 82, 14)]


def render(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 400, "height": 400})
        for name, (emoji, c1, c2) in AVATARS.items():
            pg.set_viewport_size({"width": 400, "height": 400})
            pg.set_content(PAGE % {"w": 400, "h": 400, "bg": f"linear-gradient(135deg,{c1},{c2})", "grid": 0,
                                   "top": "52%", "size": 220, "dsize": 0, "deco": "", "main": emoji})
            pg.screenshot(path=str(out / f"avatar-{name}.png"))
        for name, (bg, main, deco) in COVERS.items():
            pg.set_viewport_size({"width": 1600, "height": 900})
            spans = "".join(f'<div class="d" style="left:{x}%;top:{y}%;transform:rotate({r}deg)">{e}</div>'
                            for e, (x, y, r) in zip(deco, SPOTS))
            pg.set_content(PAGE % {"w": 1600, "h": 900, "bg": bg, "grid": 0.55, "top": "50%", "size": 380,
                                   "dsize": 130, "deco": spans, "main": main})
            pg.screenshot(path=str(out / f"cover-{name}.jpg"), type="jpeg", quality=90)
        b.close()


if __name__ == "__main__":
    render(Path(sys.argv[1]))
