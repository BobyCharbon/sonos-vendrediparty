"""Exigences Apple du 14.11.2026 — confidentialité, données, compte (App Store Review Guidelines 5.1.1, 5.1.2, 4.8, 3.1) :
- manifestes PrivacyInfo.xcprivacy : chaque « required reason API » appelée par une cible est déclarée dans SA cible ;
- chaque permission demandée par le code a son texte NS…UsageDescription, en français ;
- suppression du compte dans l'app (5.1.1(v)) : tout part, photos de profil du Storage comprises ;
- politique de confidentialité : données ajoutées depuis le 9.11 (covoiturage, heure des réponses et des votes, liens
  nommés, demandes d'accord, « Nouveau compte ») et RGPD / DSA pour la France, la Belgique et le Luxembourg ;
- 4.8 : connexion par SMS seulement (aucun service tiers) → « Se connecter avec Apple » n'est pas exigé ;
- 3.1.1 : aucun contenu numérique vendu (billets d'événements réels : 3.1.3(e))."""
import glob
import json
import os
import plistlib
import re

import httpx
import pytest

from app import account_auth, accounts as accounts_mod


def read(path: str) -> str:
    return open(path, encoding="utf-8").read()


# ── project.yml (XcodeGen), lu sans dépendance : sources et textes d'autorisation de chaque cible ──
def targets() -> dict[str, dict]:
    out: dict[str, dict] = {}
    current = None
    in_sources = False
    in_targets = False
    for line in read("ios/project.yml").splitlines():
        if line.startswith("targets:"):
            in_targets = True
            continue
        if not in_targets or not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^  [A-Za-z]+:\s*$", line):
            current = line.strip()[:-1]
            out[current] = {"sources": [], "text": ""}
            in_sources = False
            continue
        if current is None:
            continue
        out[current]["text"] += line + "\n"
        if re.match(r"^    [a-zA-Z]", line):
            in_sources = line.strip() == "sources:"
            continue
        m = re.match(r"^      - path: (\S+)", line)
        if in_sources and m:
            out[current]["sources"].append(m.group(1))
    return out


def swift_of(target: dict) -> str:
    files = []
    for src in target["sources"]:
        path = os.path.join("ios", src)
        files += [path] if path.endswith(".swift") else glob.glob(os.path.join(path, "**", "*.swift"), recursive=True)
    return "\n".join(read(f) for f in files)


REQUIRED_REASON_APIS = {
    "NSPrivacyAccessedAPICategoryUserDefaults": r"\bUserDefaults\b|@AppStorage",
    "NSPrivacyAccessedAPICategoryFileTimestamp": r"attributesOfItem|creationDate|modificationDate|getattrlist|\bfstat\(|\blstat\(",
    "NSPrivacyAccessedAPICategorySystemBootTime": r"systemUptime|mach_absolute_time",
    "NSPrivacyAccessedAPICategoryDiskSpace": r"volumeAvailableCapacity|systemFreeSize|statfs|\bsystemSize\b",
    "NSPrivacyAccessedAPICategoryActiveKeyboards": r"activeInputModes",
}
MANIFESTS = {"Party": "ios/Party/PrivacyInfo.xcprivacy", "PartyShare": "ios/PartyShare/PrivacyInfo.xcprivacy",
             "PartyWidgets": "ios/PartyWidgets/PrivacyInfo.xcprivacy", "PartyTV": "ios/PartyTV/PrivacyInfo.xcprivacy"}


@pytest.mark.parametrize("name", sorted(MANIFESTS))
def test_each_target_declares_the_required_reason_apis_it_calls(name):
    target = targets()[name]
    assert target["sources"], name
    code = swift_of(target)
    with open(MANIFESTS[name], "rb") as f:
        manifest = plistlib.load(f)
    assert manifest["NSPrivacyTracking"] is False and manifest["NSPrivacyTrackingDomains"] == []
    declared = {e["NSPrivacyAccessedAPIType"]: e["NSPrivacyAccessedAPITypeReasons"] for e in manifest["NSPrivacyAccessedAPITypes"]}
    for category, pattern in REQUIRED_REASON_APIS.items():
        if re.search(pattern, code):
            assert declared.get(category), f"{name} appelle {category} sans le déclarer"
    # UserDefaults de l'app seule (CA92.1) : aucun groupe d'apps partagé (le partage passe par le trousseau).
    if "NSPrivacyAccessedAPICategoryUserDefaults" in declared:
        assert declared["NSPrivacyAccessedAPICategoryUserDefaults"] == ["CA92.1"]
        assert "suiteName" not in code


# Ce que le code appelle → le texte d'autorisation qu'iOS exige (sinon : refus en revue, ou l'app se ferme).
PERMISSIONS = [
    (r"DataScannerViewController|AVCaptureDevice|UIImagePickerController", "NSCameraUsageDescription"),
    (r"requestRecordPermission|AVAudioRecorder", "NSMicrophoneUsageDescription"),
    (r"SFSpeechRecognizer", "NSSpeechRecognitionUsageDescription"),
    (r"CNContactStore", "NSContactsUsageDescription"),
    (r"EKEventStore", "NSCalendarsFullAccessUsageDescription"),
    (r"EKEventStore", "NSCalendarsUsageDescription"),
    (r"PhotosPicker|PHPhotoLibrary", "NSPhotoLibraryUsageDescription"),
    (r"CLLocationManager", "NSLocationWhenInUseUsageDescription"),
    (r"CMMotionManager|CMMotionActivityManager|CMPedometer", "NSMotionUsageDescription"),
    (r"CBCentralManager", "NSBluetoothAlwaysUsageDescription"),
    (r"NWBrowser|NetServiceBrowser", "NSLocalNetworkUsageDescription"),
    (r"LAContext", "NSFaceIDUsageDescription"),
    # Appui long sur une image de la page › « Ajouter à Photos » : WKWebView garde ce menu sauf allowsLinkPreview = false.
    (r"WKWebView\(", "NSPhotoLibraryAddUsageDescription"),
    # « Enregistrer » de la visionneuse photo des Discussions (avis 48a0eefd44ce).
    (r"PHAssetChangeRequest", "NSPhotoLibraryAddUsageDescription"),
]


def usage_texts(target: dict) -> dict[str, str]:
    return dict(re.findall(r"^\s+(NS\w+UsageDescription): \"([^\"]+)\"", target["text"], re.M))


@pytest.mark.parametrize("name", ["Party", "PartyTV"])
def test_every_permission_asked_by_the_code_has_its_text_in_french(name):
    target = targets()[name]
    code = swift_of(target)
    texts = usage_texts(target)
    for pattern, key in PERMISSIONS:
        if pattern == r"WKWebView\(" and "allowsLinkPreview = false" in code:
            continue
        if re.search(pattern, code):
            assert key in texts, f"{name} : {key} manque ({pattern})"
    for key, text in texts.items():
        assert len(text) >= 30 and text.startswith(("Pour", "Seulement")), (key, text)
    assert "ATTrackingManager" not in code  # aucun suivi publicitaire, donc jamais la demande de suivi


def test_feedback_sends_the_device_so_the_manifest_declares_diagnostics():
    assert "systemVersion" in read("ios/Party/Feedback/FeedbackAI.swift")
    with open(MANIFESTS["Party"], "rb") as f:
        types = {e["NSPrivacyCollectedDataType"] for e in plistlib.load(f)["NSPrivacyCollectedDataTypes"]}
    assert "NSPrivacyCollectedDataTypeOtherDiagnosticData" in types
    assert "Other Diagnostic Data" in read("ios/appstore/app-store-connect.md")


# ── 5.1.1(v) : suppression du compte ──
def fake_supabase(delete_status=204, photos=("1.jpg", "2.jpg")):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u1"})
        if request.url.path == "/storage/v1/object/list/profile-photos":
            return httpx.Response(200, json=[{"name": n, "id": n} for n in photos])
        if request.url.path == "/rest/v1/rpc/delete_my_account":
            return httpx.Response(delete_status, json={"message": "last_admin"} if delete_status >= 400 else None)
        return httpx.Response(200, json=[])

    return accounts_mod.Accounts(b"s", httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_account_deletion_also_removes_the_profile_photos_from_the_storage():
    acc, seen = fake_supabase()
    account_auth.AccountAuth(acc).delete_account("t" * 30, "SUPPRIMER")
    calls = [(m, p) for m, p, _ in seen]
    assert calls.index(("POST", "/storage/v1/object/list/profile-photos")) < calls.index(("POST", "/rest/v1/rpc/delete_my_account"))
    removal = [b for m, p, b in seen if m == "DELETE" and p == "/storage/v1/object/profile-photos"]
    assert removal == [{"prefixes": ["u1/1.jpg", "u1/2.jpg"]}]
    assert next(b for m, p, b in seen if p == "/storage/v1/object/list/profile-photos")["prefix"] == "u1"
    assert calls.index(("POST", "/rest/v1/rpc/delete_my_account")) < calls.index(("DELETE", "/storage/v1/object/profile-photos"))


def test_a_refused_deletion_keeps_the_photo():
    acc, seen = fake_supabase(delete_status=400)
    with pytest.raises(accounts_mod.AccountError, match="dernier administrateur"):
        account_auth.AccountAuth(acc).delete_account("t" * 30, "SUPPRIMER")
    assert not [p for m, p, _ in seen if m == "DELETE"]


def test_every_row_linked_to_an_account_goes_with_it():
    """delete_my_account efface auth.users : tout le reste suit par les clés étrangères (cascade, ou set null pour
    « qui a fait » sur une ligne d'un autre). Une clé sans « on delete » bloquerait toute suppression de compte."""
    sql = "\n".join(read(f) for f in sorted(glob.glob("supabase/migrations/*.sql")))
    refs = re.findall(r"references\s+(?:public\.)?profiles\s*\(\s*id\s*\)[^,\n]*|references\s+auth\.users\s*\(\s*id\s*\)[^,\n]*", sql)
    assert len(refs) > 100
    assert all(re.search(r"on delete (cascade|set null)", r) for r in refs), [r for r in refs if "on delete" not in r]
    assert "id uuid primary key references auth.users (id) on delete cascade" in sql  # profiles
    # Données ajoutées récemment : la ligne de la personne part avec elle.
    for table in ("event_carpool", "event_join_requests", "calendar_feeds", "calendar_feed_events", "wallet_passes"):
        block = re.search(rf"create table if not exists public\.{table} \((.*?)\n\);", sql, re.S).group(1)
        assert re.search(r"user_id uuid not null (unique )?references public\.profiles ?\(id\) on delete cascade", block), table
    for table in ("rsvps", "date_votes"):  # heure de la réponse (updated_at) et du vote (voted_at) : sur la ligne
        block = re.search(rf"create table {table} \((.*?)\n\);", sql, re.S).group(1)
        assert "user_id uuid not null references profiles (id) on delete cascade" in block, table


# ── Politique de confidentialité (web et iPhone, même texte) ──
def web_paragraphs() -> list[str]:
    body = read("web/events/src/app/privacy.tsx").split("const BLOCKS", 1)[1].split("export default", 1)[0]
    contact = read("web/events/src/lib/contact.ts")
    email = re.search(r"SUPPORT_EMAIL = '([^']+)'", contact).group(1)
    who = re.search(r"RESPONSIBLE = '([^']+)'", contact).group(1)
    found = re.findall(r"'((?:[^'\\]|\\.)*)'|`([^`]*)`", body)
    return [(a or b).replace("${SUPPORT_EMAIL}", email).replace("${RESPONSIBLE}", who).replace("’", "'") for a, b in found]


def swift_paragraphs() -> list[str]:
    body = read("ios/Party/Settings/Account/SignInView.swift").split("static let sections", 1)[1].split("var moderation", 1)[0]
    return re.findall(r'"((?:[^"\\]|\\.)*)"', body)


def test_iphone_privacy_text_is_word_for_word_the_web_text():
    web, ios = web_paragraphs(), swift_paragraphs()
    assert len(web) > 50 and web == ios


def test_privacy_policy_tells_the_data_added_since_november_9_and_the_eu_rules():
    text = " ".join(web_paragraphs())
    for words in ("Covoiturage", "ville de départ", "l'heure de chaque réponse et de chaque vote", "Nouveau compte",
                  "Liens nommés", "accord de l'organisateur", "tes photos de profil", "calendrier abonné",
                  "RGPD", "Bases légales", "portabilité", "CNIL", "Autorité de protection des données", "CNPD",
                  "DSA", "point de contact unique", "Combien de temps", "support@vendrediparty.ch"):
        assert words in text, words
    assert "25 novembre 2026" in read("web/events/src/app/privacy.tsx")  # éditeur établi en France (25.11)


# ── 4.8 et 3.1 ──
CODE = [p for pattern in ("app/**/*.py", "app/static/**/*.js", "app/static/**/*.html", "web/events/src/**/*.ts",
                          "web/events/src/**/*.tsx", "ios/**/*.swift") for p in glob.glob(pattern, recursive=True)
        if "/vendor/" not in p and "/quizbank/" not in p]  # questions de quiz : des titres de chansons


def test_login_is_by_sms_only_so_sign_in_with_apple_is_not_required():
    """4.8 n'exige « Se connecter avec Apple » que si l'app propose un service de connexion tiers ou social (Google,
    Facebook…). Party se connecte par SMS (compte propre, Supabase/Twilio) : rien de tiers. La connexion Spotify de
    l'hôte relie un lecteur de musique, elle ne crée ni n'ouvre de compte Party."""
    third_party = re.compile(r"signInWithOAuth|signInWithIdToken|GIDSignIn|GoogleSignIn|FBSDKLogin|LoginManager\(\)|"
                             r"/auth/v1/authorize|ASWebAuthenticationSession")
    assert [p for p in CODE if third_party.search(read(p))] == []
    assert "/auth/v1/otp" in read("app/account_auth.py")


def test_nothing_digital_is_sold_outside_in_app_purchase():
    """3.1.1 : aucun achat dans l'app (pas de StoreKit, aucun prestataire de paiement) ; les billets sont ceux
    d'événements réels payés à l'organisateur hors de l'app (3.1.3(e)) ; les pièces de jeu ne s'achètent jamais."""
    pay = re.compile(r"\bStoreKit\b|SKPaymentQueue|Product\.purchase|stripe|Stripe|payrexx|datatrans|sumup|checkout\.session")
    assert [p for p in CODE if pay.search(read(p))] == []
    assert "in-app-payments" not in read("ios/project.yml") and "com.apple.developer.in-app" not in read("ios/project.yml")
    pet = "\n".join(read(p) for p in glob.glob("app/pet*.py"))
    assert not re.search(r"price_chf|chf|CHF|stripe|twint", pet)  # pièces et objets du jeu : jamais d'argent réel
