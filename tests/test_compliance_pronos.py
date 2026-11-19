"""Conformité des Pronos et des confettis, ex-patates (revue du 18.11.2026, conformite-patates : 🔴 1-8, 🟠).

- 🔴 8 : aucun mot d'argent, de pari ni de casino dans les textes des écrans des Pronos (web et iPhone) ; les
  identifiants de code et les commentaires ne comptent pas, seuls les textes (chaînes et texte JSX) ;
- 🔴 7 : CGU 2026-11-18 « Pronos et confettis » (web et iPhone, même texte) et confidentialité à jour ;
- 🔴 6 : drapeau `patates` (éteint en prod tant que la version n'est pas acceptée) et notes de revue Apple ≤ 4 000 ;
- 🔴 5 : questionnaire d'âge « Simulated Gambling » Frequent, Gambling Non.
Ces tests lisent les fichiers : ils échouent tant que les écrans, le drapeau ou le rappel ne sont pas en place."""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def plain(text: str) -> str:
    return text.replace("’", "'")


WEB_SCREENS = ["web/events/src/app/pronos.tsx", "web/events/src/app/group/[id]/pronos.tsx",
               *glob.glob(str(ROOT / "web/events/src/app/prono*/**/*.tsx"), recursive=True),
               *glob.glob(str(ROOT / "web/events/src/components/pronos/**/*.tsx"), recursive=True)]
IOS_SCREENS = glob.glob(str(ROOT / "ios/Party/Pronos/**/*.swift"), recursive=True)


def screen_files() -> list[Path]:
    files = {(ROOT / p).resolve() for p in WEB_SCREENS + IOS_SCREENS}
    return sorted(p for p in files if p.exists())


def texts(src: str, swift: bool) -> list[str]:
    """Les textes d'un fichier : chaînes ('…', "…", `…`, \"\"\"…\"\"\") et, pour le web, texte JSX entre balises.
    Commentaires retirés ; le reste du code (identifiants, clés) est ignoré."""
    found, code, i, n = [], [], 0, len(src)
    quotes = ('"',) if swift else ("'", '"', "`")
    while i < n:
        if src.startswith("//", i):
            i = src.find("\n", i) if src.find("\n", i) != -1 else n
        elif src.startswith("/*", i):
            end = src.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif swift and src.startswith('"""', i):
            end = src.find('"""', i + 3)
            end = n if end == -1 else end
            found.append(src[i + 3:end])
            code.append(" ")
            i = end + 3
        elif src[i] in quotes:
            q, j = src[i], i + 1
            while j < n and src[j] != q and not (src[j] == "\n" and q != "`"):
                j += 2 if src[j] == "\\" else 1
            found.append(src[i + 1:j])
            code.append(" ")
            i = j + 1
        else:
            code.append(src[i])
            i += 1
    if not swift:
        found += re.findall(r">([^<>{}=;()]+)<", "".join(code))
    return found


# Mots d'argent, de pari et de casino (conformite-patates, partie 2 ; contrat Pronos v2, « Vocabulaire »).
FORBIDDEN = re.compile(
    r"\b(?:pari|parie|parier|pariez|parié|parieur|parieurs|mise|mises|miser|misez|misé|cagnotte|cote|cotes|"
    r"jackpot|gain|gains|balles|francs?|chf|thunes|jetons?|coins?|pièces?|casino|bookmaker|tapis|quitte ou double|"
    r"gagner des confettis|gagne des confettis|gagner des patates|gagne des patates|pot)\b|€|💰|💵|🎰|🎲|🪙", re.IGNORECASE)
ALLOWED = re.compile(r"mises? à jour|mises? en (?:avant|page|place|forme)", re.IGNORECASE)


def test_the_prono_screens_exist():
    names = {p.name for p in screen_files()}
    assert {"pronos.tsx", "new.tsx", "[id].tsx", "[token].tsx"} <= names, names
    assert {"PronosListView.swift", "PronoDetailView.swift", "PronoNewView.swift"} <= names, names


def test_no_money_betting_or_casino_word_on_the_prono_screens():
    bad = []
    for path in screen_files():
        for text in texts(path.read_text(encoding="utf-8"), swift=path.suffix == ".swift"):
            for m in FORBIDDEN.finditer(ALLOWED.sub(" ", text)):
                if m.group(0) == "paris":
                    continue
                bad.append(f"{path.relative_to(ROOT)} : « {m.group(0)} » dans « {text.strip()[:80]} »")
    assert not bad, "\n".join(bad)


def test_the_word_scanner_reads_texts_not_code_nor_comments():
    web = "// une mise en commentaire\nconst mise = 1; /* cote */ const t = 'Ta mise'; x = <T>La cote du jour</T>;"
    assert [w for t in texts(web, swift=False) for w in FORBIDDEN.findall(t)] == ["mise", "cote"]
    swift = '/// cagnotte\nlet pot = 2\nText("Lancer 5 🎊") ; Text("Mise à jour")'
    assert [w for t in texts(swift, swift=True) for w in FORBIDDEN.findall(ALLOWED.sub(" ", t))] == []


def test_the_no_value_reminder_is_on_the_web_and_the_iphone():
    """Rappel fixe sous chaque sac (🟠) : les confettis ne valent rien."""
    reminder = "Les confettis n'ont aucune valeur"
    web = " ".join(plain(read(str(p.relative_to(ROOT)))) for p in screen_files() if p.suffix == ".tsx")
    web += plain(read("web/events/src/lib/pronos.ts")) if (ROOT / "web/events/src/lib/pronos.ts").exists() else ""
    ios = " ".join(plain(p.read_text(encoding="utf-8")) for p in screen_files() if p.suffix == ".swift")
    assert reminder in web and reminder in ios


PRONO_TERMS = [
    "Pronos et confettis",
    "pour l'honneur",
    "Les confettis sont gratuits et n'ont aucune valeur.",
    "Ils ne s'achètent pas, ne se vendent pas, ne s'échangent pas et ne se transfèrent pas",
    "Il est interdit de régler un prono ou des confettis en argent, en boissons, en objets",
    "Jamais de prono sur l'alcool",
    "peut être suspendu",
    "Apple et Google ne sont ni organisateurs ni sponsors",
]


def terms_sections(web: bool) -> list[tuple[str, list[str]]]:
    if web:
        src = read("web/events/src/lib/terms.ts")
        blocks = re.findall(r"title: '([^']*)',\s*paragraphs: \[(.*?)\n    \]", src, re.S)
        return [(plain(t), [plain(p) for p in re.findall(r"'((?:[^'\\]|\\.)*)'", body)]) for t, body in blocks]
    src = read("ios/Party/Settings/Moderation/TermsView.swift").split("static let sections", 1)[1].split("var body", 1)[0]
    blocks = re.findall(r'\("([^"]*)", \[(.*?)\n        \]\)', src, re.S)
    return [(t, re.findall(r'"((?:[^"\\]|\\.)*)"', body)) for t, body in blocks]


def test_terms_2026_11_18_have_the_prono_section_word_for_word_on_web_and_iphone():
    web, ios = terms_sections(web=True), terms_sections(web=False)
    assert len(web) >= 8 and web == ios
    section = " ".join(p for t, ps in web if t == "Pronos et confettis" for p in ps) + " Pronos et confettis"
    for words in PRONO_TERMS:
        assert words in section, words
    assert "TERMS_UPDATED = '18 novembre 2026'" in read("web/events/src/lib/terms.ts")
    assert 'static let updated = "18 novembre 2026"' in read("ios/Party/Settings/Moderation/TermsView.swift")
    assert "Zicou" not in read("web/events/src/lib/terms.ts")  # Zicou reste en bêta


def test_the_database_asks_everyone_to_accept_the_terms_of_2026_11_18():
    versions = []
    for path in sorted(glob.glob(str(ROOT / "supabase/migrations/*.sql"))):
        versions += re.findall(r"set terms_version = '(\d{4}-\d\d-\d\d)'", Path(path).read_text(encoding="utf-8"))
    assert versions and versions[-1] == "2026-11-18"
    assert (ROOT / "supabase/prod/2026-11-18-cgu-pronos-patates-apply.sql").exists()
    assert (ROOT / "supabase/prod/2026-11-18-cgu-pronos-patates-rollback.sql").exists()


def test_privacy_policy_tells_what_the_pronos_keep_on_web_and_iphone():
    web = plain(read("web/events/src/app/privacy.tsx"))
    ios = read("ios/Party/Settings/Account/SignInView.swift")
    for text in (web, ios):
        for words in ("Pronos : tes pronos, tes réponses, les confettis que tu lances et ceux que tu ramasses",
                      "l'historique de ton sac (toi seul le vois)", "tes contestations", "tes réactions",
                      "Rien de tout cela n'est envoyé à un tiers.", "Ton sac de confettis et son historique",
                      "pronos et confettis", "18 novembre 2026"):
            assert words in text, words


def test_the_patates_flag_exists_and_is_served():
    features = read("app/features.py")
    assert "def patates_enabled" in features and "PATATES_ENABLED" in features
    assert '"patates"' in read("app/main.py")


def test_review_notes_say_pronos_are_not_in_this_version_and_carry_no_code():
    """19.11 : Pronos et confettis gardés en test (PRONOS_ENABLED / PATATES_ENABLED éteints en prod) : les notes pour Apple
    ne les décrivent pas comme une fonction à tester, elles disent qu'ils ne sont pas dans cette version."""
    notes = read("ios/appstore/review-notes.txt").strip()
    assert len(notes) <= 4000
    assert "Not in this version" in notes and "Pronos" in notes.split("Not in this version")[1].split("\n")[0]
    assert "PRONOS (" not in notes and "Simulated Gambling" not in notes and "Confetti" not in notes
    assert not re.search(r"\b\d{6}\b", notes)  # jamais le code du compte de démo


def test_age_rating_declares_no_simulated_gambling_while_pronos_are_off():
    asc = read("ios/appstore/app-store-connect.md")
    assert "| Simulated Gambling | **Aucun** (19.11) |" in asc and "| Gambling (argent réel) | Non |" in asc
    checklist = read("docs/app-store/checklist-envoi.md")
    assert "Simulated Gambling : **None**" in checklist and "Gambling : **Non**" in checklist
    for text in (asc, checklist):
        assert "PATATES_ENABLED" in text  # la version qui les ouvrira repassera par là
