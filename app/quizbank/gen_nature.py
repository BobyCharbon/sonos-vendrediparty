"""Nature : Espace, Animaux, Corps humain (tables vérifiées + questions rédigées)."""

import random

from . import make, pick
from . import data_animaux as A
from . import data_corps as C
from . import data_espace as E
from .gen_divert import _chrono, _decades, _years, decade
from .gen_geo import _comparisons


def de_les(x: str) -> str:
    return "des " + x[4:] if x.startswith("les ") else "de " + x


def century(y: int) -> str:
    from .gen_histoire import century as c
    return c(y // 100 + 1)


def cap(x: str) -> str:
    return x[0].upper() + x[1:]


def _espace():
    out = []
    names = [cap(p[0]) for p in E.PLANETS]
    ordinals = {1: "1re", 2: "2e", 3: "3e", 4: "4e", 5: "5e", 6: "6e", 7: "7e", 8: "8e"}
    for name, rank, diam, dist, year, kind in E.PLANETS:
        out.append(make("espace", f"Quelle est la {ordinals[rank]} planète en partant du Soleil ?", cap(name), pick(f"prank-{name}", names, cap(name)), 1 if rank <= 4 else 2))
        out.append(make("espace", f"À quel rang se trouve {name} en partant du Soleil ?", ordinals[rank], pick(f"prk-{name}", list(ordinals.values()), ordinals[rank]), 2))
        out.append(make("espace", f"Quel type de planète est {name} ?", cap(kind), pick(f"ptype-{name}", ["Tellurique (rocheuse)", "Géante gazeuse", "Géante de glace", "Planète naine"],
                                                                                       cap(kind), key=lambda x: x.split(" (")[0].lower()), 2))
        if 1 < rank < 8:
            prev, nxt = E.PLANETS[rank - 2][0], E.PLANETS[rank][0]
            out.append(make("espace", f"Quelle planète se trouve entre {prev} et {nxt} ?", cap(name), pick(f"pbetw-{name}", names, cap(name)), 2))
        years = {88: "88 jours", 225: "225 jours", 365: "365 jours", 687: "687 jours", 4333: "12 ans", 10759: "29 ans", 30687: "84 ans", 60190: "165 ans"}
        out.append(make("espace", f"Combien de temps dure une année (un tour du Soleil) sur {name} ?", years[year], pick(f"pyear-{name}", list(years.values()), years[year]), 3))
    out += _comparisons("espace", E.PLANETS, lambda p: cap(p[0]), lambda p: p[2], "Laquelle de ces planètes est la plus grande ?",
                        "Laquelle de ces planètes est la plus petite ?", 60, "pdiam", 1.15)
    out += _comparisons("espace", E.PLANETS, lambda p: cap(p[0]), lambda p: p[3], "Laquelle de ces planètes est la plus éloignée du Soleil ?",
                        "Laquelle de ces planètes est la plus proche du Soleil ?", 70, "pdist", 1.3)
    for fact, planet in E.PLANET_FACTS:
        out.append(make("espace", f"Quelle planète {fact} ?", cap(planet), pick(f"pfact-{fact}", names, cap(planet)), 2))
    moon_planets = ["La Terre", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton"]
    for moon, planet in E.MOONS:
        out.append(make("espace", f"Autour de quel astre tourne {moon} ?", cap(planet), pick(f"moon-{moon}", moon_planets, cap(planet)), 1 if moon == "la Lune" else 2 if planet in ("Jupiter", "Saturne", "Mars") else 3))
    by_p = {}
    for moon, planet in E.MOONS:
        by_p.setdefault(planet, []).append(moon)
    for planet, moons in by_p.items():
        others = [m for m, p in E.MOONS if p != planet]
        for m in moons:
            out.append(make("espace", f"Lequel de ces satellites tourne autour de {planet} ?", cap(m), [cap(o) for o in pick(f"moonr-{m}", others, m)], 2))
    consts = list(dict.fromkeys(c for _, c in E.STARS))
    for star, const in E.STARS:
        out.append(make("espace", f"Dans quelle constellation se trouve {star} ?", cap(const), [cap(c) for c in pick(f"star-{star}", consts, const)], 2 if star in ("Bételgeuse", "Rigel", "l'étoile Polaire", "Sirius") else 3))
        others = [s for s, c in E.STARS if c != const]
        out.append(make("espace", f"Quelle étoile appartient à la constellation : {const} ?", cap(star), [cap(o) for o in pick(f"starr-{star}", others, star)], 3))
    objs = [o for _, o in E.MESSIER]
    for code, obj in E.MESSIER:
        out.append(make("espace", f"Quel objet céleste porte le numéro {code} du catalogue de Messier ?", cap(obj), [cap(o) for o in pick(f"mes-{code}", objs, obj)], 3))
        out.append(make("espace", f"Quel est le numéro Messier de {obj} ?", code, pick(f"mesr-{code}", [c for c, _ in E.MESSIER], code), 3))
    for ev, y, agency in E.MISSIONS:
        out.append(make("espace", f"En quelle année a eu lieu {ev} ?", str(y), _years(y, f"msy-{ev}"), 2 if y in (1957, 1961, 1969) else 3))
        out.append(make("espace", f"Dans quelle décennie a eu lieu {ev} ?", decade(y), _decades(y, f"msd-{ev}"), 2))
        out.append(make("espace", f"Quelle agence ou quel pays a mené : {ev} ?", agency, pick(f"msa-{ev}", E.AGENCIES, agency, key=lambda x: x.split(" (")[-1]), 2))
    out += _chrono("espace", E.MISSIONS, lambda m: cap(m[0]), lambda m: m[1], 320, "mchrono-esp", 4,
                   "Lequel de ces événements spatiaux a eu lieu en premier ?", "Lequel de ces événements spatiaux est le plus récent ?")
    out += _comparisons("espace", E.STAR_DIST, lambda x: cap(x[0]), lambda x: x[1], "Laquelle de ces étoiles est la plus proche de nous ?",
                        "Laquelle de ces étoiles est la plus éloignée de nous ?", 160, "stardist", 1.6)
    out += _comparisons("espace", E.PLANETS, lambda p: cap(p[0]), lambda p: p[4], "Sur laquelle de ces planètes l'année est-elle la plus longue ?",
                        "Sur laquelle de ces planètes l'année est-elle la plus courte ?", 60, "pyear", 1.3)
    for dw, where in E.DWARFS:
        out.append(make("espace", f"Où se trouve la planète naine {dw} ?", cap(where), [cap(x) for x in pick(f"dw-{dw}", [w for _, w in E.DWARFS] + ["la ceinture de Van Allen"], where)], 3))
    for d, q, a, w in E.WRITTEN:
        out.append(make("espace", q, a, w, d))
    return out


def _animaux():
    out = []
    classes = [A.MA, A.OI, A.RE, A.AM, A.PO, A.IN, A.AR, A.CR, A.MO]
    near = {A.MA: [A.PO, A.OI, A.RE], A.OI: [A.MA, A.RE, A.AM], A.RE: [A.AM, A.MA, A.PO], A.AM: [A.RE, A.PO, A.MA], A.PO: [A.MA, A.AM, A.RE],
            A.IN: [A.AR, A.CR, A.MO], A.AR: [A.IN, A.CR, A.MO], A.CR: [A.IN, A.MO, A.AR], A.MO: [A.CR, A.PO, A.IN]}
    for animal, cls in A.CLASSES:
        d = 2 if animal in A.TRICKY else 1
        out.append(make("animaux", f"À quelle classe appartient {animal} ?", cls, near[cls], d))
    rng = random.Random("aniclass")
    by_cls = {}
    for animal, cls in A.CLASSES:
        by_cls.setdefault(cls, []).append(animal)
    for cls, animals in by_cls.items():
        others = [a for a, c in A.CLASSES if c != cls]
        for a in animals[:14]:
            label = {A.MA: "un mammifère", A.OI: "un oiseau", A.RE: "un reptile", A.AM: "un amphibien", A.PO: "un poisson", A.IN: "un insecte",
                     A.AR: "un arachnide", A.CR: "un crustacé", A.MO: "un mollusque"}[cls]
            out.append(make("animaux", f"Lequel de ces animaux est {label} ?", cap(a), [cap(o) for o in rng.sample(others, 3)], 2 if a in A.TRICKY else 1))
    for animal, diet in A.DIETS:
        out.append(make("animaux", f"Quel est le régime alimentaire de {animal} ?", diet, pick(f"diet-{animal}", ["Carnivore", "Herbivore", "Omnivore", "Insectivore"], diet), 1))
    regions = ["Afrique", "Asie", "Amérique", "Océanie", "Europe", "Arctique", "Antarctique"]
    for animal, reg in A.ORIGINS:
        out.append(make("animaux", f"Dans quelle région du monde vit {animal} à l'état sauvage ?", reg, pick(f"orig-{animal}", regions, reg), 1 if reg in ("Océanie", "Antarctique", "Arctique") else 2))
    by_reg = {}
    for animal, reg in A.ORIGINS:
        by_reg.setdefault(reg, []).append(animal)
    for reg, animals in by_reg.items():
        others = [a for a, r in A.ORIGINS if r != reg]
        where = {"Afrique": "en Afrique", "Asie": "en Asie", "Amérique": "en Amérique", "Océanie": "en Océanie", "Europe": "en Europe",
                 "Arctique": "dans l'Arctique", "Antarctique": "en Antarctique"}[reg]
        for a in animals:
            out.append(make("animaux", f"Lequel de ces animaux vit {where} ?", cap(a), [cap(o) for o in pick(f"origr-{a}", others, a)], 2))
    babies = [b for _, b in A.BABIES]
    for adult, baby in A.BABIES:
        out.append(make("animaux", f"Comment s'appelle le petit de {adult.replace('le ', '', 1) if False else adult} ?", cap(baby), [cap(b) for b in pick(f"baby-{adult}", babies, baby)], 1))
        out.append(make("animaux", f"{cap(baby)} est le petit de quel animal ?", cap(adult), [cap(a) for a in pick(f"babyr-{adult}", [a for a, _ in A.BABIES], adult)], 2))
    fem = [f for _, f in A.FEMALES]
    for male, female in A.FEMALES:
        out.append(make("animaux", f"Comment s'appelle la femelle de {male} ?", cap(female), [cap(f) for f in pick(f"fem-{male}", fem, female)], 2))
        out.append(make("animaux", f"Quel est le mâle de {female} ?", cap(male), [cap(m) for m in pick(f"femr-{male}", [m for m, _ in A.FEMALES], male)], 2))
    cries = [c for _, c in A.CRIES]
    for animal, cry in A.CRIES:
        verb = cry.split()[1]
        out.append(make("animaux", f"Que fait {animal} quand il ou elle crie ?", cry, pick(f"cry-{animal}", cries, cry, key=lambda x: x.split()[1]), 2))
        out.append(make("animaux", f"Quel animal {verb} ?", cap(animal), [cap(a) for a in pick(f"cryr-{animal}", [a for a, _ in A.CRIES], animal)], 2))
    homes = [h for _, h in A.HOMES]
    for animal, home in A.HOMES:
        out.append(make("animaux", f"Où vit ou dort {animal} ?", home, pick(f"home-{animal}", homes, home), 1))
    weighed = [m for m in A.MEASURES]
    out += _comparisons("animaux", weighed, lambda m: cap(m[0]), lambda m: m[1], "Lequel de ces animaux est le plus lourd ?",
                        "Lequel de ces animaux est le plus léger ?", 260, "aniw", 1.8)
    fast = [m for m in A.MEASURES if m[2]]
    out += _comparisons("animaux", fast, lambda m: cap(m[0]), lambda m: m[2], "Lequel de ces animaux est le plus rapide ?",
                        "Lequel de ces animaux est le plus lent ?", 180, "anis", 1.5)
    for d, q, a, w in A.WRITTEN:
        out.append(make("animaux", q, a, w, d))
    return out


def _corps():
    out = []
    regions = list(dict.fromkeys(r for _, r in C.BONES))
    for bone, reg in C.BONES:
        out.append(make("corps", f"Dans quelle partie du corps se trouve {bone} ?", reg, pick(f"bone-{bone}", regions, reg), 2))
    by_reg = {}
    for bone, reg in C.BONES:
        by_reg.setdefault(reg, []).append(bone)
    for reg, bones in by_reg.items():
        others = [b for b, r in C.BONES if r != reg]
        for b in bones:
            out.append(make("corps", f"Quel os se trouve dans cette partie du corps : {reg.lower()} ?", cap(b), [cap(o) for o in pick(f"boner-{b}", others, b)], 2))
    mregions = list(dict.fromkeys(r for _, r in C.MUSCLES))
    for m, reg in C.MUSCLES:
        out.append(make("corps", f"Où se trouve {m} ?", reg, pick(f"mus-{m}", mregions, reg), 2))
        others = [x for x, r in C.MUSCLES if r != reg]
        out.append(make("corps", f"Quel muscle ou tendon se trouve dans cette partie du corps : {reg.lower()} ?", cap(m), [cap(o) for o in pick(f"musr-{m}", others, m)], 2))
    funcs = [f for _, f in C.ORGANS]
    for organ, f in C.ORGANS:
        out.append(make("corps", f"Quel est le rôle principal de {organ} ?", f, pick(f"org-{organ}", funcs, f), 2))
        out.append(make("corps", f"Quel organe a pour rôle de : {f[0].lower() + f[1:]} ?", cap(organ), [cap(o) for o in pick(f"orgr-{organ}", [o for o, _ in C.ORGANS], organ)], 2))
    systems = list(dict.fromkeys(s for _, s in C.SYSTEMS))
    for organ, system in C.SYSTEMS:
        out.append(make("corps", f"À quel système appartiennent {organ} ?" if organ.startswith("les ") else f"À quel système appartient {organ} ?",
                        system, pick(f"sys-{organ}", systems, system), 1))
        others = [o for o, s in C.SYSTEMS if s != system]
        out.append(make("corps", f"Lequel de ces éléments fait partie du système {system.split(' (')[0].lower()} ?", cap(organ), [cap(o) for o in pick(f"sysr-{organ}", others, organ)], 2))
    areas = [a for _, a in C.SPECIALTIES]
    for spec, area in C.SPECIALTIES:
        out.append(make("corps", f"De quoi s'occupe {spec[0].lower() + spec[1:]} ?", area, pick(f"spec-{spec}", areas, area), 1 if spec in ("Un cardiologue", "Un dermatologue", "Un pédiatre", "Un ophtalmologue") else 2))
        out.append(make("corps", f"Quel spécialiste consulter pour : {area[0].lower() + area[1:]} ?", spec, pick(f"specr-{spec}", [s for s, _ in C.SPECIALTIES], spec), 2))
    meanings = [m for _, m in C.ROOTS]
    for root, meaning in C.ROOTS:
        out.append(make("corps", f"Que signifie la racine médicale « {root} » ?", meaning, pick(f"root-{root}", meanings, meaning), 2))
        out.append(make("corps", f"Quelle racine médicale désigne : {meaning[0].lower() + meaning[1:]} ?", f"« {root} »", [f"« {r} »" for r in pick(f"rootr-{root}", [r for r, _ in C.ROOTS], root)], 3))
    parts = list(dict.fromkeys(p for _, p in C.DISEASES))
    for dis, part in C.DISEASES:
        out.append(make("corps", f"Quelle partie du corps touche {dis} ?", part, pick(f"dis-{dis}", parts, part), 2))
    by_part = {}
    for dis, part in C.DISEASES:
        by_part.setdefault(part, []).append(dis)
    for part, diss in by_part.items():
        others = [d for d, p in C.DISEASES if p != part]
        for dis in diss:
            out.append(make("corps", f"Quelle maladie ou affection touche : {part[0].lower() + part[1:]} ?", cap(dis), [cap(o) for o in pick(f"disr-{dis}", others, dis)], 2))
    causes = ["Un virus", "Une bactérie", "Un parasite", "Une anomalie génétique", "Un champignon"]
    for dis, cause in C.CAUSES:
        out.append(make("corps", f"Quelle est la cause de {dis} ?", cause, pick(f"cause-{dis}", causes, cause), 2))
    vits = [v for _, v in C.VITAMINS]
    for dis, vit in C.VITAMINS:
        out.append(make("corps", f"Quelle carence provoque {dis} ?", f"Un manque de {vit[0].lower() + vit[1:]}", [f"Un manque de {v[0].lower() + v[1:]}" for v in pick(f"vit-{dis}", vits, vit)], 2))
    for sense, organ in C.SENSES:
        out.append(make("corps", f"Quel organe est associé au sens suivant : {sense.lower()} ?", organ, pick(f"sense-{sense}", [o for _, o in C.SENSES], organ), 1))
        out.append(make("corps", f"Quel sens est associé à cet organe : {organ.lower()} ?", sense, pick(f"senser-{sense}", [s for s, _ in C.SENSES], sense), 1))
    roles = [r for _, r in C.CELLS]
    for cell, role in C.CELLS:
        out.append(make("corps", f"Quel est le rôle {de_les(cell)} ?", role, pick(f"cell-{cell}", roles, role), 2))
        out.append(make("corps", f"Quelles cellules ont pour rôle de : {role[0].lower() + role[1:]} ?", cap(cell), [cap(c) for c in pick(f"cellr-{cell}", [c for c, _ in C.CELLS], cell)], 2))
    glands = list(dict.fromkeys(g for _, g in C.HORMONES))
    for h, g in C.HORMONES:
        out.append(make("corps", f"Quel organe ou glande produit {h} ?", g, pick(f"horm-{h}", glands, g), 2))
        others = [x for x, gg in C.HORMONES if gg != g]
        out.append(make("corps", f"Quelle hormone est produite par cet organe : {g[0].lower() + g[1:]} ?", cap(h), [cap(o) for o in pick(f"hormr-{h}", others, h)], 3))
    for food, nut in C.NUTRIENTS:
        out.append(make("corps", f"Quel nutriment domine dans {food} ?", nut, pick(f"nut-{food}", ["Les glucides", "Les lipides", "Les protéines", "Les fibres"], nut), 1))
    for t, role, n in C.TEETH:
        out.append(make("corps", f"À quoi servent principalement {t[0].lower() + t[1:]} ?", role, pick(f"teeth-{t}", [r for _, r, _ in C.TEETH] + ["Aspirer"], role), 2))
        out.append(make("corps", f"Combien un adulte a-t-il de {t.split()[1]} (dents de sagesse comprises) ?", n, pick(f"teethn-{t}", ["4", "8", "12", "16", "6"], n), 3))
    for term, meaning in C.ANATOMY_TERMS:
        out.append(make("corps", f"En anatomie, que signifie « {term} » ?", meaning, pick(f"anat-{term}", [m for _, m in C.ANATOMY_TERMS], meaning), 3))
    for ev, y in C.DISCOVERIES:
        out.append(make("corps", f"En quelle année a eu lieu {ev} ?", str(y), _years(y, f"disc-{ev}"), 3))
        out.append(make("corps", f"À quel siècle a eu lieu {ev} ?" if y < 1900 else f"Dans quelle décennie a eu lieu {ev} ?",
                        century(y) if y < 1900 else decade(y), [century(y + k) for k in (-200, -100, 100)] if y < 1900 else _decades(y, f"discd-{ev}"), 2))
    out += _chrono("corps", C.DISCOVERIES, lambda d: cap(d[0]), lambda d: d[1], 300, "discchrono", 8,
                   "Laquelle de ces avancées médicales est la plus ancienne ?", "Laquelle de ces avancées médicales est la plus récente ?")
    for d, q, a, w in C.WRITTEN:
        out.append(make("corps", q, a, w, d))
    return out


def generate():
    return _espace() + _animaux() + _corps()
