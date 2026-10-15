"""Petits outils de français pour les questions générées (articles, « de », drapeaux)."""

VOWELS = "aeiouyhâàéèêëîïôöûüAEIOUYHÂÀÉÈÊËÎÏÔÖÛÜ"


def de(x: str) -> str:
    """« de » + nom avec son article : le Japon → du Japon, les Pays-Bas → des Pays-Bas, Oman → d'Oman."""
    if x.startswith("le "):
        return "du " + x[3:]
    if x.startswith("les "):
        return "des " + x[4:]
    if x.startswith(("la ", "l'")):
        return "de " + x
    return ("d'" if x[0] in VOWELS else "de ") + x


def bare(x: str) -> str:
    """Le nom sans article, avec une majuscule : les États-Unis → États-Unis."""
    for art in ("le ", "la ", "les ", "l'"):
        if x.startswith(art):
            x = x[len(art):]
            break
    return x[0].upper() + x[1:]


def flag(iso: str) -> str:
    """Code pays (ISO 3166) → emoji du drapeau."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())


def fmt_int(n: int) -> str:
    """12345 → « 12 345 » (espace fine insécable)."""
    return f"{n:,}".replace(",", " ")
