"""Scripts et styles de la page pour l'app App Store (« PartyStore », refus Apple 1.4.3, contrôle du 26.11).

L'app App Store ne reçoit ni le code des jeux cachés (store_app.HIDDEN_GAMES) ni un mot de boisson : la page de l'app
pointe vers /static-store/<fichier>, qui sert le même fichier que /static/ après avoir retiré :
- les blocs entre `<store-cut>` et `</store-cut>` (une ligne de marque chacun, en commentaire du langage du fichier) et
  toute ligne de JS qui finit par `// <store-cut/>` (ou `<!-- store-cut -->` dans un texte HTML) ; une ligne `// <store> code`
  devient `code` (version de l'app), une ligne `<!-- <store> html -->` d'un texte HTML devient `html` ;
- les commentaires (lignes `// …` et fin de ligne ` // …` du JS, `/* … */` du CSS) ;
et en remplaçant chaque adresse « /static/….js|css » d'un script par « /static-store/… » (chargements différés).
Le site, l'app BETA et Android reçoivent /static/ tel quel. Test : tests/test_store_static.py (page + tous les scripts
servis à PartyStore, aucun mot de CODE_DRINK_RE).
"""
import re
from functools import lru_cache
from pathlib import Path

from . import store_app

PREFIX = "/static-store/"
# Mots de boisson, de jeu d'argent ou de drogue interdits dans tout ce que l'app reçoit (store_app.DRINK_RE sans « bar »,
# mot de l'interface : barre d'onglets, de progression).
CODE_DRINK_RE = re.compile(store_app.DRINK_RE.pattern.replace(r"|\bbars?\b", ""), re.IGNORECASE)
CUT_JS = re.compile(r"^[ \t]*//[ \t]*<store-cut>.*?^[ \t]*//[ \t]*</store-cut>[^\n]*\n?", re.S | re.M)
CUT_CSS = re.compile(r"^[ \t]*/\*[ \t]*<store-cut>.*?^[ \t]*/\*[ \t]*</store-cut>[^\n]*\n?", re.S | re.M)
CUT_HTML = re.compile(r"^[ \t]*<!--[ \t]*<store-cut>.*?<!--[ \t]*</store-cut>[ \t]*-->[^\n]*\n?", re.S | re.M)
CUT_LINE = re.compile(r"^[^\n]*(?://[ \t]*<store-cut/>|<!--[ \t]*store-cut[ \t]*-->)[ \t]*\n", re.M)
STORE_LINE = re.compile(r"^([ \t]*)//[ \t]*<store>[ \t]?", re.M)
STORE_HTML_LINE = re.compile(r"^([ \t]*)<!-- <store> (.*?) -->[ \t]*$", re.M)
LINE_COMMENT = re.compile(r"^[ \t]*//[^\n]*\n", re.M)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
JS_URL = re.compile(r"""(["'`])/static/([\w./-]+\.(?:js|css))(?=["'`?])""")


def _trailing_comment(line: str) -> str:
    """Retire « // commentaire » en fin de ligne de code, seulement hors de toute chaîne."""
    if " // " not in line:
        return line
    quote, i = None, 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif line.startswith(" // ", i):
            return line[:i].rstrip()
        i += 1
    return line


def js(text: str) -> str:
    text = CUT_LINE.sub("", CUT_HTML.sub("", CUT_JS.sub("", text)))
    text = STORE_HTML_LINE.sub(r"\1\2", STORE_LINE.sub(r"\1", text))
    text = LINE_COMMENT.sub("", text)
    text = "\n".join(_trailing_comment(line) for line in text.split("\n"))
    return JS_URL.sub(lambda m: f"{m.group(1)}{PREFIX}{m.group(2)}", text)


def css(text: str) -> str:
    return CSS_COMMENT.sub("", CUT_CSS.sub("", text))


def html(text: str) -> str:
    """Page de l'app App Store : blocs coupés, scripts et styles servis par /static-store/."""
    text = CUT_HTML.sub("", text)
    return re.sub(r"""(["'])/static/([\w./-]+\.(?:js|css))(?=["'?])""", rf"\1{PREFIX}\2", text)


@lru_cache(maxsize=256)
def _render(path: str, mtime: float) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return js(text) if path.endswith(".js") else css(text)


def render(path: Path) -> str:
    return _render(str(path), path.stat().st_mtime)
