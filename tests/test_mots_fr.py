"""Dictionnaire de « Débuts de mots » (Méninges, app/static/brain/mots/) : complet, propre et cohérent.

- les mots pièges écrits à la main (tests/data/mots_fr_controle.txt : conjugaisons complètes, pluriels en -aux,
  féminins, composés, œ/ç, mots courants et récents) sont acceptés ;
- chaque fichier <abc>.txt est trié, sans doublon, bien normalisé et conforme à index.json ;
- la normalisation est la même dans le jeu (syllabes.js), le script de construction et ce test ;
- aucun début grossier n'est proposé comme lettres de départ ;
- pas de noms propres courants (sauf s'ils sont aussi des noms communs : « marie » du verbe marier, « paris »),
  ni de graphies fautives ou obsolètes, ni de verbe + pronom (« abonne-toi »).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOTS = ROOT / 'app' / 'static' / 'brain' / 'mots'
SYLLABES_JS = ROOT / 'app' / 'static' / 'brain' / 'games' / 'syllabes.js'
CONTROLE = Path(__file__).resolve().parent / 'data' / 'mots_fr_controle.txt'

MIN_PIEGES = 3000
MIN_COVERAGE = 0.995
MAX_FILE_BYTES = 300_000
LINE = re.compile(r"[a-z]{3}(?:[a-z'-]*[a-z])?")
RUDE_STARTS = ('con', 'cul', 'bit', 'put', 'nic', 'enc', 'bai', 'sod', 'zob', 'teu', 'sex', 'por')

pytestmark = pytest.mark.skipif(not (MOTS / 'index.json').exists(), reason='dictionnaire non construit')


def normalize(word: str) -> str:
    """Normalisation de dico_spec.md, écrite ici indépendamment du jeu et du script de construction."""
    w = word.lower().replace('œ', 'oe').replace('æ', 'ae')
    w = ''.join(ch for ch in unicodedata.normalize('NFD', w) if unicodedata.category(ch) != 'Mn')
    w = re.sub(r"[’‘ʼ´`]", "'", w)
    return ' '.join(w.split())


@lru_cache(maxsize=1)
def index() -> dict:
    return json.loads((MOTS / 'index.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def files() -> dict[str, list[str]]:
    return {f.stem: f.read_text(encoding='utf-8').splitlines() for f in sorted(MOTS.glob('*.txt'))
            if f.name != 'LICENCES.txt'}


@lru_cache(maxsize=1)
def words() -> frozenset[str]:
    return frozenset(w for lines in files().values() for w in lines)


def accepted(word: str) -> bool:
    return normalize(word) in words()


def pieges() -> list[str]:
    lines = CONTROLE.read_text(encoding='utf-8').splitlines()
    return [w for w in (line.strip() for line in lines) if w and not w.startswith('#')]


# ── Mots pièges ──

def test_control_list_is_large_and_well_formed():
    forms = pieges()
    assert len(forms) >= MIN_PIEGES
    normalized = [normalize(w) for w in forms]
    assert len(set(normalized)) == len(normalized), 'doublons après normalisation'
    bad = [w for w, n in zip(forms, normalized) if not LINE.fullmatch(n)]
    assert not bad, bad[:20]


def test_hand_picked_tricky_words_are_accepted():
    forms = pieges()
    missing = sorted({normalize(w) for w in forms if not accepted(w)})
    coverage = 1 - len(missing) / len(forms)
    assert coverage >= MIN_COVERAGE, f'couverture {coverage:.2%}, manquants : {missing[:60]}'


@pytest.mark.parametrize('word', [
    # pluriels, féminins, invariables
    'chevaux', 'journaux', 'travaux', 'vitraux', 'bijoux', 'genoux', 'yeux', 'cieux', 'aïeux', 'messieurs',
    'bonshommes', 'œufs', 'belle', 'vieille', 'vieil', 'nouvel', 'folle', 'fraîche', 'grecque', 'aiguë', 'actrice',
    # conjugaisons : tous les temps, verbes irréguliers
    'allions', 'irions', 'aille', 'allâmes', 'fussions', 'fûtes', 'eûmes', 'aies', 'sachions', 'veuillez',
    'vînmes', 'tînt', 'naquîmes', 'vécûmes', 'résolûmes', 'assoyons', 'asseyions', 'assiérai', 'acquièrent',
    'mourûmes', 'cueillerai', 'enverrai', 'faudrait', 'plût', 'haïssons', 'mangeâmes', 'commençâmes',
    'appelleront', 'jetterais', 'lèverions', 'paierai', 'payerai', 'nettoierez', 'finissiez', 'choisîtes',
    # participes accordés
    'prises', 'mises', 'faites', 'ouvertes', 'peintes', 'conduites', 'reçues', 'dues', 'nées', 'assises',
    # œ, æ, ç
    'cœur', 'sœurs', 'nœud', 'vœux', 'œuvre', 'manœuvre', 'œsophage', 'fœtus', 'curriculum', 'garçon',
    'leçons', 'reçu', 'français', 'hameçon', 'aperçûmes',
    # composés à trait d'union, élision dans un mot
    'grand-mère', 'grands-pères', 'arc-en-ciel', 'arcs-en-ciel', 'porte-monnaie', 'après-midi', 'chef-d\'œuvre',
    'chefs-d\'œuvre', 'aujourd\'hui', 'quelqu\'un', 'presqu\'île', 'peut-être', 'week-end', 'rendez-vous',
    'sèche-cheveux', 'lave-vaisselle', 'gratte-ciel', 'tire-bouchon', 'pique-nique', 'celle-ci', 'ceux-là',
    # courants et récents
    'pizza', 'pizzas', 'sandwich', 'sandwichs', 'ordinateur', 'téléphoner', 'smartphone', 'selfie', 'selfies',
    'tchatter', 'liker', 'zapper', 'bloguer', 'texto', 'emoji', 'hashtag', 'podcast', 'youtubeur',
    'influenceuse', 'télétravail', 'vapoter', 'startup', 'covid', 'raclette', 'tartiflette', 'apéro',
    # noms propres qui sont aussi des noms communs ou des formes verbales
    'marie', 'paris', 'pierre', 'jean', 'suisse', 'chine', 'japon', 'macron', 'brésil', 'argentine',
])
def test_word_is_accepted(word):
    assert accepted(word), f'« {word} » ({normalize(word)}) refusé'


# ── Pas de noms propres, graphies fautives, verbe + pronom ──

@pytest.mark.parametrize('word', [
    'france', 'allemagne', 'angleterre', 'europe', 'afrique', 'amérique', 'italie', 'espagne',
    'russie', 'égypte', 'maroc', 'algérie', 'mongolie', 'palestine', 'californie', 'gibraltar', 'himalaya',
    'sahara', 'venise', 'mexico', 'berlin', 'lyon', 'marseille', 'toulouse', 'genève', 'lausanne', 'zurich',
    'bruxelles', 'tokyo', 'moscou', 'madrid', 'lisbonne', 'perpignan',
    'nicolas', 'sophie', 'stéphane', 'christophe', 'sébastien', 'mathieu', 'nathalie', 'philippe', 'bernard',
    'xavier', 'jérôme', 'aurélien', 'mélanie', 'amélie', 'pauline', 'hélène', 'céline', 'émilie', 'martine',
    'thérèse', 'jeanne', 'henri', 'hubert',
    'facebook', 'youtube', 'netflix', 'instagram', 'whatsapp', 'samsung', 'microsoft', 'windows', 'linux',
    'renault', 'peugeot', 'toyota', 'airbus', 'boeing', 'pokemon', 'javascript', 'sarkozy', 'hitler', 'mozart',
    'picasso', 'shakespeare', 'charlemagne', 'allah', 'jéhovah', 'mahomet',
])
def test_proper_noun_is_refused(word):
    assert not accepted(word), f'nom propre accepté : « {word} »'


@pytest.mark.parametrize('word', [
    # graphies obsolètes ou fautives (Wiktionnaire « alternative, obsolete », listes générées)
    'commancer', 'colonnel', 'asyle', 'artrose', 'synonime', 'pantouffle', 'naviger', 'treuver',
    'pataugeairent', 'composerassiez', 'trepassont', 'harcellement', 'cauchemard', 'ascenceur',
    # verbe + pronom, élisions, abréviations
    'abonne-toi', 'aurait-il', 'était-elle', 'allons-y', 'jusqu\'au', 'lorsqu\'on', 'qqch',
    # anglais de sous-titres
    'emergency', 'glasses', 'field',
])
def test_false_word_is_refused(word):
    assert not accepted(word), f'faux mot accepté : « {word} »'


# ── Fichiers ↔ index.json ──

def test_files_match_index():
    idx, data = index(), files()
    assert set(data) == set(idx['prefixes']), 'fichiers et index.json ne listent pas les mêmes débuts'
    wrong = {abc: (len(lines), idx['prefixes'][abc]['n']) for abc, lines in data.items()
             if len(lines) != idx['prefixes'][abc]['n']}
    assert not wrong, list(wrong.items())[:10]
    assert idx['total'] == sum(len(lines) for lines in data.values()) == len(words())


def test_index_entries_are_consistent():
    for abc, p in index()['prefixes'].items():
        assert re.fullmatch(r'[a-z]{3}', abc), abc
        assert 0 <= p['common'] <= p['n'], abc
        assert 1 <= p['rank'] <= 5, abc


def test_files_are_sorted_unique_small_and_normalized():
    min_len = index().get('minLength', 4)
    for abc, lines in files().items():
        assert lines == sorted(set(lines)), f'{abc}.txt : pas trié ou doublons'
        assert (MOTS / f'{abc}.txt').stat().st_size < MAX_FILE_BYTES, abc
        bad = [w for w in lines if not (w.startswith(abc) and LINE.fullmatch(w) and len(w) >= min_len
                                        and normalize(w) == w)]
        assert not bad, f'{abc}.txt : {bad[:10]}'


def test_licences_are_listed():
    text = (MOTS / 'LICENCES.txt').read_text(encoding='utf-8')
    for name in ('Grammalecte', 'Morphalou', 'Lexique'):
        assert name in text


# ── Normalisation ──

NORMALIZE_CASES = {
    'Œuvre': 'oeuvre', 'cœur': 'coeur', 'ex-æquo': 'ex-aequo', 'Curriculum': 'curriculum', 'GARÇON': 'garcon',
    'Élève': 'eleve', 'aujourd’hui': "aujourd'hui", '  pizza  ': 'pizza', 'naïf': 'naif', 'aiguë': 'aigue',
    'Île': 'ile', 'où': 'ou', 'chef-d’œuvre': "chef-d'oeuvre", 'Noël': 'noel', 'çà': 'ca',
}


@pytest.mark.parametrize('raw, expected', NORMALIZE_CASES.items())
def test_normalization(raw, expected):
    assert normalize(raw) == expected


def test_build_script_normalizes_like_the_spec():
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        import build_mots_fr
    finally:
        sys.path.remove(str(ROOT / 'tools'))
    assert {raw: build_mots_fr.normalize(raw) for raw in NORMALIZE_CASES} == NORMALIZE_CASES


@pytest.mark.skipif(not shutil.which('node'), reason='node absent')
def test_game_normalizes_like_the_spec():
    source = SYLLABES_JS.read_text(encoding='utf-8')
    fn = re.search(r'function normalize\(s\) \{.*?\n  \}', source, re.S)
    assert fn, 'normalize() introuvable dans syllabes.js'
    script = f'{fn.group(0)}\nconst cases = {json.dumps(list(NORMALIZE_CASES))};\n' \
             'console.log(JSON.stringify(cases.map(normalize)));'
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(out.stdout) == list(NORMALIZE_CASES.values())


# ── Débuts grossiers ──

def test_rude_starts_are_never_offered():
    prefixes = index()['prefixes']
    offered = [abc for abc in RUDE_STARTS if abc in prefixes and prefixes[abc].get('start', True)]
    assert not offered, offered


def test_rude_words_stay_valid():
    for word in ('concert', 'culture', 'putois', 'niche', 'encore', 'baignoire', 'sexuel', 'porte'):
        assert accepted(word), word


def test_game_safety_net_matches_index():
    source = SYLLABES_JS.read_text(encoding='utf-8')
    net = re.search(r'const RUDE = new Set\(\[(.*?)\]\)', source)
    assert net, 'filet RUDE introuvable dans syllabes.js'
    prefixes = index()['prefixes']
    for abc in re.findall(r"'([a-z]{3})'", net.group(1)):
        assert prefixes.get(abc, {}).get('start', False) is False, abc
