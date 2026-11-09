"""Assemble la maquette autonome : police Bricolage (sous-ensemble woff2) et QR en SVG intégrés au HTML."""
import base64
import io
import sys
from pathlib import Path

import qrcode
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).resolve().parent
FONT_SRC = Path(sys.argv[1])
QR_TEXT = "PARTY-BAR-DEMO-LEA"


def font_base64(text: str) -> str:
    font = TTFont(FONT_SRC)
    # Valeurs par défaut de la police : graisse 800, comme les titres de Party.
    static = instancer.instantiateVariableFont(font, {"wght": 800, "opsz": None, "wdth": None})
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(static)
    buf = io.BytesIO()
    static.flavor = "woff2"
    static.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def qr_svg(data: str) -> str:
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    path = "".join(f"M{x} {y}h1v1h-1z" for y, row in enumerate(matrix) for x, on in enumerate(row) if on)
    return (f'<svg viewBox="0 0 {n} {n}" shape-rendering="crispEdges" role="img" aria-label="QR de démonstration">'
            f'<path fill="#15102A" d="{path}"/></svg>')


def main() -> None:
    template = (HERE / "template.html").read_text(encoding="utf-8")
    glyphs = "".join(sorted(set(template))) + "0123456789"
    html = template.replace("{{FONT}}", font_base64(glyphs)).replace("{{QR}}", qr_svg(QR_TEXT))
    out = HERE / "bar-soiree.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out} : {len(html) // 1024} Ko")


if __name__ == "__main__":
    main()
