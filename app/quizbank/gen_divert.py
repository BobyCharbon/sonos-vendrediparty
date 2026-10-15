"""Divertissement : cinéma & séries, musique, jeux vidéo, BD & mangas (tables + générateurs)."""

import random

from . import make, pick
from .data_bd import ALBUMS, BD_CHARACTERS, BD_SERIES, SUPERHEROES, WRITTEN_BD
from .data_cinema import FILM_ROLES, FILMS, SERIES, SERIES_CHARACTERS, WRITTEN_CINEMA
from .data_jeux import CONFLICTS, CONSOLES, GAME_CHARACTERS, GAMES, WRITTEN_JEUX
from .data_musique import MUSIC_ARTISTS, SONGS, WRITTEN_MUSIQUE


def decade(y: int) -> str:
    return f"Années {y // 10 * 10}"


def _years(y: int, seed: str) -> list[str]:
    rng = random.Random(seed)
    ds = [-6, -4, -3, -2, 2, 3, 4, 6, -8, 8]
    rng.shuffle(ds)
    return [str(y + d) for d in ds]


def _decades(y: int, seed: str) -> list[str]:
    dec = y // 10 * 10
    opts = [decade(dec + k * 10) for k in (-30, -20, -10, 10, 20) if 1900 <= dec + k * 10 <= 2020]
    return pick(seed, opts, decade(y))


def _chrono(theme, items, label, year, n, seed, gap, q_first, q_last):
    rng = random.Random(seed)
    out, tries = [], 0
    while len(out) < n and tries < n * 60:
        tries += 1
        four = rng.sample(items, 4)
        first = rng.random() < 0.55
        srt = sorted(four, key=year, reverse=not first)
        if abs(year(srt[1]) - year(srt[0])) < gap:
            continue
        q = make(theme, q_first if first else q_last, label(srt[0]), [label(x) for x in srt[1:]], 2 if abs(year(srt[1]) - year(srt[0])) > 15 else 3)
        if q:
            out.append(q)
    return out


def _cinema():
    out = []
    directors = list(dict.fromkeys(f[2] for f in FILMS))
    for title, y, director, fame in FILMS:
        out.append(make("cinema", f"Qui a réalisé « {title} » ?", director, pick(f"dir-{title}", directors, director), fame))
        out.append(make("cinema", f"En quelle année est sorti « {title} » ?", str(y), _years(y, f"fy-{title}"), 3))
        out.append(make("cinema", f"Dans quelle décennie est sorti « {title} » ?", decade(y), _decades(y, f"fd-{title}"), 2 if fame < 3 else 3))
    by_dir = {}
    for f in FILMS:
        by_dir.setdefault(f[2], []).append(f)
    titles = [f[0] for f in FILMS]
    for d, fs in by_dir.items():
        for f in fs[:3]:
            others = [t for t in titles if t not in [x[0] for x in fs]]
            out.append(make("cinema", f"Lequel de ces films a été réalisé par {d} ?", f"« {f[0]} »", [f"« {t} »" for t in pick(f"dirr-{f[0]}", others, f[0])], f[3]))
    out += _chrono("cinema", FILMS, lambda f: f"« {f[0]} »", lambda f: f[1], 200, "fchrono", 5,
                   "Lequel de ces films est sorti en premier ?", "Lequel de ces films est le plus récent ?")
    actors = list(dict.fromkeys(a for _, a, _ in FILM_ROLES))
    for role, actor, film in FILM_ROLES:
        out.append(make("cinema", f"Quel acteur ou actrice joue {role} dans « {film} » ?", actor, pick(f"role-{role}", actors, actor), 2))
    sers = [s[0] for s in SERIES]
    for title, y, country, fame in SERIES:
        out.append(make("cinema", f"Dans quelle décennie a commencé la série « {title} » ?", decade(y), _decades(y, f"sd-{title}"), fame))
        out.append(make("cinema", f"De quel pays vient la série « {title} » ?", country,
                        pick(f"sc-{title}", ["États-Unis", "Royaume-Uni", "France", "Espagne", "Allemagne", "Corée du Sud", "Canada", "Suède"], country), fame))
    out += _chrono("cinema", SERIES, lambda s: f"« {s[0]} »", lambda s: s[1], 80, "schrono", 4,
                   "Laquelle de ces séries a commencé en premier ?", "Laquelle de ces séries est la plus récente ?")
    for char, series in SERIES_CHARACTERS:
        out.append(make("cinema", f"Dans quelle série trouve-t-on le personnage {char} ?", f"« {series} »",
                        [f"« {s} »" for s in pick(f"sch-{char}", sers, series)], 2))
    for d, q, a, w in WRITTEN_CINEMA:
        out.append(make("cinema", q, a, w, d))
    return out


def _musique():
    out = []
    artists = list(dict.fromkeys(s[1] for s in SONGS))
    for title, artist, y, fame in SONGS:
        out.append(make("musique", f"Qui chante « {title} » ?", artist, pick(f"art-{title}", artists, artist), fame))
        out.append(make("musique", f"Dans quelle décennie est sortie « {title} » ({artist}) ?", decade(y), _decades(y, f"md-{title}"), 2 if fame < 3 else 3))
    by_art = {}
    for s in SONGS:
        by_art.setdefault(s[1], []).append(s)
    titles = [s[0] for s in SONGS]
    for a, ss in by_art.items():
        for s in ss[:3]:
            others = [t for t in titles if t not in [x[0] for x in ss]]
            out.append(make("musique", f"Laquelle de ces chansons est de {a} ?", f"« {s[0]} »", [f"« {t} »" for t in pick(f"artr-{s[0]}", others, s[0])], s[3]))
    out += _chrono("musique", SONGS, lambda s: f"« {s[0]} » ({s[1]})", lambda s: s[2], 220, "mchrono", 6,
                   "Laquelle de ces chansons est sortie en premier ?", "Laquelle de ces chansons est la plus récente ?")
    countries = list(dict.fromkeys(c for _, c, _ in MUSIC_ARTISTS))
    for name, country, genre in MUSIC_ARTISTS:
        out.append(make("musique", f"De quel pays vient {name} ?", country, pick(f"mc-{name}", countries, country), 2))
        if genre:
            out.append(make("musique", f"À quel genre musical associe-t-on surtout {name} ?", genre,
                            pick(f"mg-{name}", ["Rock", "Pop", "Rap / hip-hop", "Électro", "Jazz", "Reggae", "Métal", "Chanson française", "Rap français", "Soul / R&B", "Classique", "Country", "Punk"], genre), 2))
    for d, q, a, w in WRITTEN_MUSIQUE:
        out.append(make("musique", q, a, w, d))
    return out


def _jeux():
    out = []
    studios = list(dict.fromkeys(g[2] for g in GAMES))
    for title, y, studio, fame in GAMES:
        ok_studios = [s for s in studios if s not in CONFLICTS.get(studio, ())]
        out.append(make("jeux", f"Quel studio ou éditeur est derrière « {title} » ?", studio, pick(f"gs-{title}", ok_studios, studio), fame))
        out.append(make("jeux", f"En quelle année est sorti « {title} » ?", str(y), _years(y, f"gy-{title}"), 3))
        out.append(make("jeux", f"Dans quelle décennie est sorti « {title} » ?", decade(y), _decades(y, f"gd-{title}"), 2 if fame < 3 else 3))
    by_st = {}
    for g in GAMES:
        by_st.setdefault(g[2], []).append(g)
    titles = [g[0] for g in GAMES]
    for st, gs in by_st.items():
        for g in gs[:3]:
            others = [x[0] for x in GAMES if x[2] != st and x[2] not in CONFLICTS.get(st, ())]
            out.append(make("jeux", f"Lequel de ces jeux vient de {st} ?", f"« {g[0]} »", [f"« {t} »" for t in pick(f"gsr-{g[0]}", others, g[0])], g[3]))
    out += _chrono("jeux", GAMES, lambda g: f"« {g[0]} »", lambda g: g[1], 320, "gchrono", 4,
                   "Lequel de ces jeux est sorti en premier ?", "Lequel de ces jeux est le plus récent ?")
    series = list(dict.fromkeys(s for _, s in GAME_CHARACTERS))
    for char, serie in GAME_CHARACTERS:
        out.append(make("jeux", f"Dans quelle série de jeux trouve-t-on {char} ?", serie, pick(f"gc-{char}", series, serie), 2))
    by_serie = {}
    for char, serie in GAME_CHARACTERS:
        by_serie.setdefault(serie, []).append(char)
    for serie, chars in by_serie.items():
        others = [c for c, s in GAME_CHARACTERS if s != serie]
        for char in chars[:2]:
            out.append(make("jeux", f"Quel personnage vient de la série « {serie} » ?", char[0].upper() + char[1:],
                            [c[0].upper() + c[1:] for c in pick(f"gcr-{char}", others, char)], 2))
    makers = list(dict.fromkeys(c[1] for c in CONSOLES))
    for console, maker, y in CONSOLES:
        out.append(make("jeux", f"Quel constructeur a lancé la console {console} ?", maker, pick(f"cm-{console}", makers + ["Atari", "Sega", "Nintendo", "Sony", "Microsoft"], maker), 2))
        out.append(make("jeux", f"En quelle année est sortie la console {console} (première sortie) ?", str(y), _years(y, f"cy-{console}"), 3))
        out.append(make("jeux", f"Dans quelle décennie est sortie la console {console} ?", decade(y), _decades(y, f"cd-{console}"), 2))
    out += _chrono("jeux", CONSOLES, lambda c: c[0], lambda c: c[2], 60, "cchrono", 3,
                   "Laquelle de ces consoles est sortie en premier ?", "Laquelle de ces consoles est la plus récente ?")
    for d, q, a, w in WRITTEN_JEUX:
        out.append(make("jeux", q, a, w, d))
    return out


def _bd():
    out = []
    authors = list(dict.fromkeys(s[1] for s in BD_SERIES))
    countries = ["Belgique", "France", "Japon", "États-Unis", "Suisse", "Italie", "Corée du Sud"]
    for title, author, country, y, fame in BD_SERIES:
        out.append(make("bd", f"Qui a créé « {title} » ?", author, pick(f"ba-{title}", authors, author), fame))
        out.append(make("bd", f"De quel pays vient « {title} » ?", country, pick(f"bc-{title}", countries, country), fame))
        out.append(make("bd", f"Dans quelle décennie est né(e) « {title} » ?", decade(y), _decades(y, f"bdd-{title}"), 3))
    titles = [s[0] for s in BD_SERIES]
    for char, serie in BD_CHARACTERS:
        out.append(make("bd", f"Dans quelle BD ou quel manga trouve-t-on {char} ?", f"« {serie} »", [f"« {t} »" for t in pick(f"bch-{char}", titles, serie)], 2))
    by_bd = {}
    for char, serie in BD_CHARACTERS:
        by_bd.setdefault(serie, []).append(char)
    for serie, chars in by_bd.items():
        others = [c for c, s in BD_CHARACTERS if s != serie]
        for char in chars[:3]:
            out.append(make("bd", f"Quel personnage vient de « {serie} » ?", char[0].upper() + char[1:],
                            [c[0].upper() + c[1:] for c in pick(f"bcr-{char}", others, char)], 2))
    for serie, albums in ALBUMS.items():
        for album in albums:
            out.append(make("bd", f"À quelle série appartient l'album « {album} » ?", serie, pick(f"alb-{album}", list(ALBUMS), serie), 2))
    rng = random.Random("manga")
    mangas = [s for s in BD_SERIES if s[2] == "Japon"]
    others_bd = [s for s in BD_SERIES if s[2] != "Japon" and s[0] not in ("Akira", "Radiant")]
    for i in range(90):
        if i % 2:
            m = rng.choice(mangas)
            out.append(make("bd", "Laquelle de ces séries est un manga japonais ?", f"« {m[0]} »", [f"« {x[0]} »" for x in rng.sample(others_bd, 3)], 1))
        else:
            b = rng.choice(others_bd)
            out.append(make("bd", "Laquelle de ces séries n'est pas un manga japonais ?", f"« {b[0]} »", [f"« {x[0]} »" for x in rng.sample(mangas, 3)], 1))
    heroes = [h for h, _, _ in SUPERHEROES]
    ids = [i for _, i, _ in SUPERHEROES]
    for hero, identity, pub in SUPERHEROES:
        out.append(make("bd", f"Quelle est l'identité secrète de {hero} ?", identity, pick(f"sh-{hero}", ids, identity), 2))
        out.append(make("bd", f"Quel super-héros se cache derrière {identity} ?", hero, pick(f"shr-{hero}", heroes, hero), 2))
        out.append(make("bd", f"Chez quel éditeur est né {hero} ?", pub, pick(f"shp-{hero}", ["Marvel", "DC Comics", "Image Comics", "Dark Horse"], pub), 2))
    out += _chrono("bd", BD_SERIES, lambda s: f"« {s[0]} »", lambda s: s[3], 300, "bchrono", 6,
                   "Laquelle de ces séries est la plus ancienne ?", "Laquelle de ces séries est la plus récente ?")
    for d, q, a, w in WRITTEN_BD:
        out.append(make("bd", q, a, w, d))
    return out


def generate():
    return _cinema() + _musique() + _jeux() + _bd()
