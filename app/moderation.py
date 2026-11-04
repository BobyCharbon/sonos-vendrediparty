"""Filtre de contenu commun à toute l'app (Apple 1.2, Google UGC) : textes libres des joueurs.

Même algorithme que la base (private.moderation_verdict, migration 20261104200000_moderation.sql) : la base l'applique
d'office aux messages (Discussions, messages directs, discussions d'événement), aux surnoms et aux noms de groupe ;
ce module sert au serveur Party (prénoms des invités, affichés sur la TV) et au Compagnon (noms, mots, offres, vitrine).

Règle par type de texte :
- noms et textes courts publics (« name », « word », « offer », « showcase ») : REFUS de tout mot haineux, sexuel ou
  injurieux, de tout lien et de tout numéro de téléphone (8 chiffres ou plus) — on choisit un autre nom ;
- messages (« message ») : les insultes d'un mot sont MASQUÉES (••••) et le message part ; propos haineux ou sexuels,
  insultes en plusieurs mots ou déguisées (s a l o p e) : REFUS. Liens et numéros restent permis (on s'en échange).

Contournements simples gérés : majuscules, accents, chiffres et signes à la place des lettres (s@l0pe), lettres
répétées (saloooope), lettres séparées (s.a.l.o.p.e), caractères invisibles."""
import re
import sys
from dataclasses import dataclass

from .moderation_terms import CATEGORIES

# Normalisation lettre pour lettre (même longueur) : la position d'un mot reste celle du texte d'origine.
ACCENTS_FROM = "àáâãäåāăąæçćčďèéêëēėęěìíîïīįłñńňòóôõöøōőœŕřśšşßťùúûüūůűÿýžźż"
ACCENTS_TO = "aaaaaaaaaacccdeeeeeeeeiiiiiilnnnooooooooorrsssstuuuuuuuyyzzz"
LEET_FROM = "0134578@$€"
LEET_TO = "oieastbase"
INVISIBLE = re.compile("[​-‏⁠﻿­]")
SUFFIX = "(s|x|e|es|en|n)?"
LINK = re.compile(r"(https?://|www\.|(^|[^a-z0-9])[a-z0-9-]+\.(com|ch|fr|de|it|net|org|io|ly|me|gg|app|xyz|info|co|tv"
                  r"|be|eu|uk|us|link|site|shop|ru|to|li)($|[^a-z0-9]))")
PHONE_DIGITS = 8
MERGE_MIN = 3
MASK = "•"

PUBLIC_KINDS = ("name", "word", "offer", "showcase")
KINDS = PUBLIC_KINDS + ("message",)
REASONS = {
    "haine": "des propos haineux",
    "sexuel": "un contenu sexuel",
    "insulte": "une insulte",
    "lien": "un lien",
    "numero": "un numéro de téléphone",
}
assert len(ACCENTS_FROM) == len(ACCENTS_TO) and len(LEET_FROM) == len(LEET_TO)
_TABLE = str.maketrans(ACCENTS_FROM + LEET_FROM, ACCENTS_TO + LEET_TO)


@dataclass(frozen=True)
class Pattern:
    category: str
    pattern: str
    phrase: bool


@dataclass(frozen=True)
class Verdict:
    ok: bool
    category: str | None
    text: str
    message: str | None


class ContentRefused(ValueError):
    """Texte refusé : le message (str(e)) se montre tel quel à la personne."""


def _repeat(word: str) -> str:
    """« salope » → s+a+l+o+p+e+ : les lettres doublées ou répétées comptent comme une seule."""
    squeezed = re.sub(r"(.)\1+", r"\1", word)
    return "".join(f"{c}+" for c in squeezed)


def compile_term(term: str) -> Pattern:
    """Une entrée de la liste (app/moderation_terms.py) → motif portable Python / PostgreSQL."""
    if term.startswith("re:"):
        return Pattern("", term[3:] + SUFFIX, False)
    if term.startswith("="):
        return Pattern("", term[1:], " " in term)
    words = term.split()
    last = words[-1]
    tail = _repeat(last[:-1]) + "[a-z]*" if last.endswith("*") else _repeat(last) + SUFFIX
    return Pattern("", "[^a-z]+".join([_repeat(w) for w in words[:-1]] + [tail]), len(words) > 1)


def patterns() -> list[Pattern]:
    return [Pattern(cat, p.pattern, p.phrase) for cat, terms in CATEGORIES for p in map(compile_term, terms)]


def _category_regex(cat: str, words_only: bool = False) -> re.Pattern:
    alts = [p.pattern for p in patterns() if p.category == cat and not (words_only and p.phrase)]
    if words_only:
        return re.compile("^(" + "|".join(alts) + ")$")
    return re.compile("(^|[^a-z])(" + "|".join(alts) + ")($|[^a-z])")


_FULL = {cat: _category_regex(cat) for cat, _ in CATEGORIES}
_WORD = {cat: _category_regex(cat, True) for cat, _ in CATEGORIES}


def clean(text: str) -> str:
    return INVISIBLE.sub("", str(text or ""))


def normalize(text: str) -> str:
    """Minuscules, sans accents, chiffres et signes ramenés aux lettres : même longueur que le texte."""
    return "".join(c.lower()[:1] or c for c in text).translate(_TABLE)


def merged(norm: str) -> str:
    """Les mots du texte séparés par une espace ; 3 lettres isolées de suite ou plus sont recollées (s a l o p e)."""
    out: list[str] = []
    run: list[str] = []
    for token in [t for t in re.split(r"[^a-z]+", norm) if t]:
        if len(token) == 1:
            run.append(token)
            continue
        out.extend(["".join(run)] if len(run) >= MERGE_MIN else run)
        run = []
        out.append(token)
    out.extend(["".join(run)] if len(run) >= MERGE_MIN else run)
    return " ".join(out)


def _hit(text: str, kind: str) -> str | None:
    words = merged(normalize(text))
    for cat, _ in CATEGORIES:
        if _FULL[cat].search(words):
            return cat
    if kind in PUBLIC_KINDS:
        low = text.lower()
        if LINK.search(low):
            return "lien"
        if sum(c.isdigit() for c in low) >= PHONE_DIGITS:
            return "numero"
    return None


def _mask_insults(text: str) -> str:
    norm = normalize(text)
    out = list(text)
    for m in re.finditer(r"[a-z]+", norm):
        if _WORD["insulte"].match(m.group()):
            out[m.start():m.end()] = MASK * (m.end() - m.start())
    return "".join(out)


def refusal(category: str, kind: str) -> str:
    reason = REASONS.get(category, "un mot interdit")
    if kind == "message":
        return f"Message non envoyé : il contient {reason}. Les règles de Party l'interdisent."
    return f"Ce texte n'est pas accepté : il contient {reason}. Choisis-en un autre."


def check(text: str, kind: str = "name") -> Verdict:
    """Verdict pour un texte de joueur. kind : name, word, offer, showcase (refus) ou message (insultes masquées)."""
    if kind not in KINDS:
        raise ValueError(f"type de texte inconnu : {kind}")
    body = clean(text)
    category = _hit(body, kind)
    if category is None:
        return Verdict(True, None, body, None)
    if kind == "message" and category == "insulte":
        masked = _mask_insults(body)
        if _hit(masked, kind) is None:
            return Verdict(True, "insulte", masked, None)
    return Verdict(False, category, body, refusal(category, kind))


def require_clean(text: str, kind: str = "name") -> str:
    """Le texte à garder (masqué au besoin) ; lève ContentRefused avec une phrase claire sinon."""
    verdict = check(text, kind)
    if not verdict.ok:
        raise ContentRefused(verdict.message)
    return verdict.text


def sql_values() -> str:
    """Bloc VALUES de private.moderation_patterns (à recopier dans la migration ; vérifié par les tests)."""
    rows = [f"  ('{p.category}', '{p.pattern}', {'true' if p.phrase else 'false'})" for p in patterns()]
    return ",\n".join(rows)


if __name__ == "__main__" and "--sql" in sys.argv:
    print(sql_values())
