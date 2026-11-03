#!/usr/bin/env python3
"""Construit le dictionnaire de « Débuts de mots » (Méninges) : app/static/brain/mots/.

Sources libres, fusionnées (toutes les formes fléchies : pluriels, féminins, toutes les conjugaisons) :
  - Grammalecte / Dicollecte v7.7, lexique des formes fléchies (MPL 2.0)
  - Morphalou 3.1, ATILF-CNRS (LGPL-LR)
  - Lexique 3.83, lexique.org (CC BY-SA 4.0) : formes + fréquences (sert aussi au compte des mots « courants »)
  - Liste Gutenberg « liste.de.mots.francais.frgut.txt » (dictionnaire ifrench-gut, Christophe Pythoud, GPL)
  - Wiktionnaire (extraction kaikki.org du Wiktionary anglais, section French ; CC BY-SA 4.0 / GFDL)
  - Hunspell fr v7.7 (MPL 2.0) : ses entrées à majuscule, avec les noms propres de Grammalecte et du Wiktionnaire,
    écartent les noms propres que Morphalou et Lexique écrivent en minuscules (angleterre, berlin, mathieu)
plus les ajouts manuels tools/mots_fr_ajouts.txt, moins les exclusions tools/mots_fr_exclus.txt.

Exclus : noms propres, prénoms, patronymes, sigles et abréviations (étiquettes npr/prn/patr/titr/nbro, toute forme
contenant une majuscule, un point, un chiffre ou un autre symbole), locutions à espace, mots de moins de 4 lettres.

Normalisation (identique au jeu, voir syllabes.js) : minuscules ; œ→oe, æ→ae ; NFD puis diacritiques retirés ;
’ → ' ; espaces en trop retirés. Lettres admises après normalisation : a-z, trait d'union, apostrophe (entre lettres).

Sortie :
  app/static/brain/mots/<abc>.txt  une forme normalisée par ligne, triées, sans doublon (début = 3 lettres a-z)
  app/static/brain/mots/index.json {"version", "total", "prefixes": {abc: {n, common, rank, start?}}}
  app/static/brain/mots/LICENCES.txt

Utilisation :
  python3 tools/build_mots_fr.py --sources <dossier>   # télécharge dans <dossier> les sources absentes
Les fichiers téléchargés ne sont que lus (jamais exécutés). Les sommes SHA-256 sont vérifiées.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "app" / "static" / "brain" / "mots"
AJOUTS = ROOT / "tools" / "mots_fr_ajouts.txt"
EXCLUS = ROOT / "tools" / "mots_fr_exclus.txt"

MIN_LEN = 4                 # le jeu demande plus que les 3 lettres du début
COMMON_FREQ = 0.5           # fréquence Lexique (par million, films ou livres) d'une forme « courante »
MAX_FILE_BYTES = 300_000
# Rareté d'un début (rank 1 facile … 5 rare) : les débuts « jouables » (au moins PLAYABLE_COMMON formes courantes)
# sont répartis en 5 parts égales selon leur nombre de formes courantes ; les autres sont rank 5.
PLAYABLE_COMMON = 10
RANKS = 5
# Débuts jamais proposés comme lettres de départ (les mots restent valides)
RUDE_STARTS = frozenset("con cul bit put nic enc bai sod zob teu sex por pd".split())

SOURCES = {
    "grammalecte": {
        "file": "lexique-grammalecte-fr-v7.7.zip",
        "url": "https://grammalecte.net/dic/lexique-grammalecte-fr-v7.7.zip",
        "sha256": "bdccf2065e252010253171000a38de84581407896b6bc60aca7d4d69dab7e4d2",
    },
    "hunspell": {
        "file": "hunspell-french-dictionaries-v7.7.zip",
        "url": "https://grammalecte.net/dic/hunspell-french-dictionaries-v7.7.zip",
        "sha256": "44314d992f94b4658c31a86ef2351724a43067531b0af3643f91bf0220eee616",
    },
    "morphalou": {
        "file": "Morphalou3.1_CSV.zip",
        "url": "https://repository.ortolang.fr/api/content/morphalou/latest/Morphalou3.1_formatCSV_toutEnUn.zip",
        "sha256": "4fc815cbf17aecdf1b47f6bbc263489a460fd8d11ae17e6b522336c72bd0e333",
    },
    "lexique383": {
        "file": "Lexique383.zip",
        "url": "http://www.lexique.org/databases/Lexique383/Lexique383.zip",
        "sha256": "e181d132b3b0d3d87efc98d376968441b517353933011cebea5366321a6024e6",
    },
    "gutenberg": {
        "file": "gutenberg.txt",
        "url": "https://raw.githubusercontent.com/chrplr/openlexicon/master/datasets-info/"
               "Liste-de-mots-francais-Gutenberg/liste.de.mots.francais.frgut.txt",
        "sha256": "9adce3934347b9405bdc12ab814c0bbb46d96cea2c9ef3e287575ea786ee037e",
    },
    "wiktionnaire": {
        "file": "kaikki-French.jsonl",
        "url": "https://kaikki.org/dictionary/French/kaikki.org-dictionary-French.jsonl",
        # extraction régénérée régulièrement : une nouvelle version demande de mettre à jour cette somme
        "sha256": "9053b1845fb3e045fa1fbe3f749122fa43e21b49bfa741cadd50255ae6ca0126",
    },
}

LICENCES = """Dictionnaire de « Débuts de mots » (Méninges) — sources et licences
Généré par tools/build_mots_fr.py (version {version}). Formes normalisées : minuscules, sans accents, œ→oe, æ→ae.

1. Grammalecte — Lexique des formes fléchies du français v7.7 (base Dicollecte)
   Olivier R., https://grammalecte.net/ — Licence MPL 2.0 (https://mozilla.org/MPL/2.0/)
   {grammalecte_url}  sha256 {grammalecte_sha}

2. Morphalou 3.1 — Lexique morphologique ouvert du français, ATILF-CNRS (Nancy), ORTOLANG
   https://www.ortolang.fr/market/lexicons/morphalou — Licence LGPL-LR (Lesser General Public License for
   Linguistic Resources). {morphalou_url}  sha256 {morphalou_sha}

3. Lexique 3.83 — B. New, C. Pallier et al., http://www.lexique.org/ — Licence CC BY-SA 4.0
   (https://creativecommons.org/licenses/by-sa/4.0/). Sert aussi aux fréquences (formes « courantes »).
   {lexique383_url}  sha256 {lexique383_sha}

4. Liste de mots français « frgut » (dictionnaire ifrench-gut de Christophe Pythoud, publiée par C. Pallier dans
   openlexicon) — Licence GNU GPL. {gutenberg_url}  sha256 {gutenberg_sha}

5. Wiktionnaire — extraction kaikki.org (wiktextract, T. Ylonen) du Wiktionary, entrées « French » —
   Licence CC BY-SA 4.0 et GFDL (https://en.wiktionary.org/wiki/Wiktionary:Copyrights)
   {wiktionnaire_url}  sha256 {wiktionnaire_sha}

6. Hunspell fr « toutes variantes » v7.7 (Dicollecte, MPL 2.0) — ses seules entrées à majuscule servent à écarter
   les noms propres des autres sources (aucun mot n'en est repris). {hunspell_url}  sha256 {hunspell_sha}

7. Ajouts et exclusions manuels du projet : tools/mots_fr_ajouts.txt, tools/mots_fr_exclus.txt.

La liste dérivée (ces fichiers .txt) est redistribuée sous les mêmes conditions (CC BY-SA 4.0 pour la part
Lexique/Wiktionnaire, MPL 2.0, LGPL-LR, GPL pour leurs parts respectives) ; seules des formes de mots sont reprises.
"""

_DIACRITICS = re.compile(r"[̀-ͯ]")
_SPACES = re.compile(r"\s+")
VALID = re.compile(r"^[a-z]{3}[a-z'-]*[a-z]$")
BAD_SEQ = re.compile(r"--|''|-'|'-")


def normalize(word: str) -> str:
    """Normalisation commune au jeu et aux contrôles."""
    w = word.lower().replace("œ", "oe").replace("æ", "ae")
    w = _DIACRITICS.sub("", unicodedata.normalize("NFD", w))
    w = re.sub(r"[’‘ʼ´`]", "'", w)
    w = re.sub(r"[‐‑‒–—]", "-", w)
    return _SPACES.sub(" ", w).strip()


def accept_raw(raw: str) -> str | None:
    """Forme source → forme normalisée, ou None (majuscule = nom propre/sigle ; symbole, chiffre, espace…)."""
    raw = raw.strip()
    if not raw or raw != raw.lower():
        return None
    w = normalize(raw)
    if len(w) < MIN_LEN or not VALID.match(w) or BAD_SEQ.search(w):
        return None
    return w


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(src_dir: Path, name: str) -> Path:
    spec = SOURCES[name]
    path = src_dir / spec["file"]
    if not path.exists():
        print(f"téléchargement {name} …", file=sys.stderr)
        urllib.request.urlretrieve(spec["url"], path)
    digest = sha256(path)
    if spec["sha256"] and digest != spec["sha256"]:
        raise SystemExit(f"{name} : somme SHA-256 inattendue ({digest}) — source modifiée, vérifier avant usage")
    spec["actual_sha256"] = digest
    return path


def zip_member(path: Path, suffix: str) -> io.TextIOWrapper:
    zf = zipfile.ZipFile(path)
    member = next(n for n in zf.namelist() if n.endswith(suffix))
    return io.TextIOWrapper(zf.open(member), encoding="utf-8", newline="")


# ── Lecteurs de sources : chacun rend un ensemble de formes normalisées ──

GRAMMALECTE_SKIP_TAGS = {"npr", "prn", "patr", "titr", "nbro", "ponc", "sign", "symb", "abr", "sig", "err"}


PROPER_TAGS = {"npr", "prn", "patr"}


def read_grammalecte(path: Path) -> tuple[set[str], set[str]]:
    """Formes du dictionnaire + noms propres (npr/prn/patr), ces derniers servant à filtrer les autres sources."""
    words, proper = set(), set()
    for line in zip_member(path, ".txt"):
        cols = line.rstrip("\n").split("\t")
        if len(cols) < 5 or not cols[0].isdigit():
            continue
        tags = set(cols[4].split())
        if tags & PROPER_TAGS:
            proper.add(normalize(cols[2]))
        if tags & GRAMMALECTE_SKIP_TAGS:
            continue
        w = accept_raw(cols[2])
        if w:
            words.add(w)
    return words, proper


def read_hunspell_proper(path: Path) -> set[str]:
    """Hunspell fr (même base Dicollecte) : seules ses entrées à majuscule servent, comme liste de noms propres."""
    zf = zipfile.ZipFile(path)
    proper = set()
    with io.TextIOWrapper(zf.open("fr-toutesvariantes.dic"), encoding="utf-8") as f:
        for line in f:
            stem = line.split("/", 1)[0].split("\t", 1)[0].strip()
            if stem[:1].isupper():
                proper.add(normalize(stem))
    return proper


def read_morphalou(path: Path) -> set[str]:
    words = set()
    reader = csv.reader(zip_member(path, "Morphalou3.1_CSV.csv"), delimiter=";")
    category = ""
    for row in reader:
        if len(row) < 10:
            continue
        if row[0]:
            category = row[2]
        if category in ("CATÉGORIE", "") or row[9] in ("GRAPHIE", ""):
            continue
        w = accept_raw(row[9])
        if w:
            words.add(w)
    return words


def read_lexique(path: Path) -> tuple[set[str], dict[str, float]]:
    words, freq = set(), defaultdict(float)
    reader = csv.DictReader(zip_member(path, "Lexique383.tsv"), delimiter="\t")
    for row in reader:
        w = accept_raw(row["ortho"])
        if not w:
            continue
        words.add(w)
        try:
            f = max(float(row["freqfilms2"] or 0), float(row["freqlivres"] or 0))
        except ValueError:
            f = 0.0
        freq[w] = max(freq[w], f)
    return words, dict(freq)


def read_gutenberg(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as f:
        return {w for w in (accept_raw(line) for line in f) if w}


WIKT_SKIP_POS = {"name", "abbrev", "symbol", "character", "prefix", "suffix", "infix", "interfix", "affix",
                 "punct", "num", "phrase", "proverb", "romanization", "circumfix", "combining_form", "contraction"}
# Sens ou formes écartés : abréviations, sigles, fautes, graphies anciennes (« asyle », « treuver »), contractions
# familières (« chuis »). Un mot ancien encore valide reste accepté s'il est dans une autre source.
WIKT_SKIP_TAGS = {"abbreviation", "acronym", "initialism", "clipping", "misspelling", "nonstandard",
                  "proper-noun", "letter", "symbol", "obsolete", "archaic", "contraction",
                  "error-unrecognized-form", "pronunciation-spelling", "eye-dialect"}
WIKT_SKIP_FORM_TAGS = WIKT_SKIP_TAGS | {"table-tags", "inflection-template", "romanization"}


def _wikt_entry_ok(entry: dict) -> bool:
    if entry.get("pos") in WIKT_SKIP_POS:
        return False
    tagged = [set(s.get("tags") or []) for s in entry.get("senses") or []]
    return not tagged or not all(t & WIKT_SKIP_TAGS for t in tagged)


def read_wiktionnaire(path: Path) -> tuple[set[str], set[str]]:
    """Formes des entrées françaises + noms propres (pos « name ») pour filtrer les autres sources."""
    words, proper = set(), set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("lang_code") != "fr":
                continue
            if entry.get("pos") == "name":
                proper.add(normalize(entry.get("word", "")))
                proper.update(normalize(fm.get("form", "")) for fm in entry.get("forms") or [])
                continue
            if not _wikt_entry_ok(entry):
                continue
            w = accept_raw(entry.get("word", ""))
            if w:
                words.add(w)
            for form in entry.get("forms") or []:
                if set(form.get("tags") or []) & WIKT_SKIP_FORM_TAGS:
                    continue
                w = accept_raw(form.get("form", ""))
                if w:
                    words.add(w)
    return words, proper


def read_list(path: Path) -> set[str]:
    """Liste manuelle : un mot par ligne, # pour les commentaires ; les mots sont normalisés."""
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        w = normalize(line)
        if len(w) >= MIN_LEN and VALID.match(w):
            out.add(w)
        else:
            print(f"ligne ignorée dans {path.name} : {line!r}", file=sys.stderr)
    return out


# ── Fusion ──

# Sources peu sûres seules (Lexique : corpus de sous-titres avec mots anglais, noms ; liste Gutenberg : formes générées
# fautives et inversions « aurait-il ») : une forme qui n'apparaît QUE dans l'une d'elles est écartée.
UNCORROBORATED_DROP = ("lexique383", "gutenberg")
REFERENCE = "grammalecte"   # dictionnaire du correcteur, le plus soigné
# Verbe + pronom (« abonne-toi », « aurait-il ») : pas un mot, sauf s'il est dans le dictionnaire de référence
# (rendez-vous, garde-à-vous, chez-moi…).
PRONOUN_TAIL = re.compile(r"-(t-)?(je|tu|il|elle|on|nous|vous|ils|elles|moi|toi|le|la|les|lui|leur|en|y|ce)$")


# Élision d'un mot-outil (« jusqu'au », « lorsqu'on ») : pas un mot, sauf dans le dictionnaire de référence
# (jusqu'au-boutiste, presqu'île, quelqu'un…).
ELISION_HEAD = re.compile(r"^(jusqu|lorsqu|puisqu|quoiqu|qu|quelqu|presqu)'")


def merge(sets: dict[str, set[str]], proper: set[str]) -> set[str]:
    """Union des sources, puis filtres de fiabilité.

    Un mot du dictionnaire de référence (Grammalecte) ou du Wiktionnaire en minuscule est toujours un nom commun
    possible (marie, pierre, chine, japon…) ; ailleurs, une forme connue seulement comme nom propre (Morphalou et
    Lexique écrivent en minuscules « angleterre », « berlin », « mathieu ») est écartée.
    """
    words: set[str] = set()
    for name, forms in sets.items():
        others = set().union(*(o for n, o in sets.items() if n != name and n not in UNCORROBORATED_DROP))
        words |= forms if name not in UNCORROBORATED_DROP else forms & others
    reference = sets.get(REFERENCE, set())
    common_nouns = reference | sets.get("wiktionnaire", set())
    proper_only = proper - common_nouns

    def keep(w: str) -> bool:
        if w in reference:
            return True
        if w in proper_only or PRONOUN_TAIL.search(w) or ELISION_HEAD.search(w):
            return False
        # apostrophe hors référence : il faut deux sources sûres (« clin-d'oeil » oui, « dev'nir » non)
        return "'" not in w or sum(w in sets.get(n, ()) for n in ("morphalou", "wiktionnaire")) == 2

    return {w for w in words if keep(w)}


# ── Écriture ──

def rank_thresholds(commons: list[int]) -> list[int]:
    """Bornes basses des rangs 1..RANKS-1 (quantiles des débuts jouables, du plus fourni au moins fourni)."""
    playable = sorted((c for c in commons if c >= PLAYABLE_COMMON), reverse=True)
    if not playable:
        return [PLAYABLE_COMMON] * (RANKS - 1)
    return [playable[min(len(playable) - 1, len(playable) * r // RANKS)] for r in range(1, RANKS)]


def rank_for(common: int, thresholds: list[int]) -> int:
    for rank, threshold in enumerate(thresholds, start=1):
        if common >= threshold:
            return rank
    return RANKS


def write_output(words: set[str], freq: dict[str, float], version: str) -> dict:
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for w in words:
        by_prefix[w[:3]].append(w)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.txt"):
        if old.name != "LICENCES.txt":
            old.unlink()
    commons = {}
    for abc in sorted(by_prefix):
        forms = sorted(by_prefix[abc])
        data = "\n".join(forms) + "\n"
        if len(data.encode()) > MAX_FILE_BYTES:
            raise SystemExit(f"{abc}.txt dépasse {MAX_FILE_BYTES} octets")
        (OUT_DIR / f"{abc}.txt").write_text(data, encoding="utf-8")
        commons[abc] = (len(forms), sum(1 for w in forms if freq.get(w, 0.0) >= COMMON_FREQ))
    thresholds = rank_thresholds([c for _, c in commons.values()])
    prefixes = {}
    for abc, (n, common) in commons.items():
        entry = {"n": n, "common": common, "rank": rank_for(common, thresholds)}
        if abc in RUDE_STARTS:
            entry["start"] = False
        prefixes[abc] = entry
    index = {"version": version, "total": len(words), "minLength": MIN_LEN, "commonFreq": COMMON_FREQ,
             "playableCommon": PLAYABLE_COMMON, "rankThresholds": thresholds,
             "prefixes": prefixes}
    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n",
                                        encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sources", type=Path, required=True, help="dossier des sources (téléchargées si absentes)")
    parser.add_argument("--skip", action="append", default=[], help="source à ignorer (ex. wiktionnaire)")
    args = parser.parse_args()
    args.sources.mkdir(parents=True, exist_ok=True)

    sets: dict[str, set[str]] = {}
    sets["lexique383"], freq = read_lexique(fetch(args.sources, "lexique383"))
    sets["grammalecte"], proper = read_grammalecte(fetch(args.sources, "grammalecte"))
    proper |= read_hunspell_proper(fetch(args.sources, "hunspell"))
    sets["morphalou"] = read_morphalou(fetch(args.sources, "morphalou"))
    sets["gutenberg"] = read_gutenberg(fetch(args.sources, "gutenberg"))
    if "wiktionnaire" not in args.skip:
        sets["wiktionnaire"], wikt_proper = read_wiktionnaire(fetch(args.sources, "wiktionnaire"))
        proper |= wikt_proper

    ajouts, exclus = read_list(AJOUTS), read_list(EXCLUS)
    words = (merge(sets, proper) | ajouts) - exclus

    digest = hashlib.sha1("\n".join(sorted(words)).encode()).hexdigest()[:10]
    version = f"{len(words)}-{digest}"
    index = write_output(words, freq, version)
    fmt = {f"{k}_url": v["url"] for k, v in SOURCES.items()}
    fmt.update({f"{k}_sha": v.get("actual_sha256", "non utilisée") for k, v in SOURCES.items()})
    (OUT_DIR / "LICENCES.txt").write_text(LICENCES.format(version=version, **fmt), encoding="utf-8")

    for name, s in sets.items():
        only = len(s - set().union(*(o for n, o in sets.items() if n != name)))
        print(f"{name:13s} {len(s):8d} formes ({only} propres à cette source)")
    union = set().union(*sets.values())
    print(f"noms propres connus {len(proper)} · écartées par les filtres {len(union - words)} · "
          f"ajouts {len(ajouts)} · exclus {len(exclus)}")
    sizes = sorted((p.stat().st_size, p.name) for p in OUT_DIR.glob("*.txt"))
    print(f"total {index['total']} formes · {len(index['prefixes'])} débuts · "
          f"{sum(s for s, _ in sizes) / 1e6:.1f} Mo · plus gros fichier {sizes[-1][1]} {sizes[-1][0]} o")


if __name__ == "__main__":
    main()
