#!/usr/bin/env python3
"""Envoi d'une version de l'app iPhone (App Store, ch.bobycharbon.party) à la revue d'Apple, par l'API App Store Connect.

Lancé par .github/workflows/ios-appstore.yml (secrets ASC_KEY_ID, ASC_ISSUER_ID, clé .p8) :
  python3 tools/appstore_submit.py check  <fichier .p8>
      lecture seule : versions, builds de l'app, notes et compte de démo de la revue (jamais le mot de passe).
  python3 tools/appstore_submit.py attach <fichier .p8> <version>
      guide PDF (docs/app-store/guide-revue-apple.pdf) en pièce jointe de la revue, à la place des anciennes.
  python3 tools/appstore_submit.py submit <fichier .p8> <version> <build>
      version modifiable (créée si besoin) ← build (traité, sans chiffrement propre), nouveautés
      (ios/appstore/whats-new-fr.txt, seulement après une 1re version publiée : Apple les refuse sur la première), notes pour les examinateurs (ios/appstore/review-notes.txt), compte de démo
      repris de la revue précédente (jamais dans le dépôt), puis envoi en revue.
Rien n'est envoyé si un fichier manque, si le build n'est pas traité ou si aucun compte de démo n'est connu.
"""
import hashlib
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from testflight_publish import api  # noqa: E402  (même jeton signé, même appel)

BUNDLE_ID = "ch.bobycharbon.party"
ROOT = pathlib.Path(__file__).resolve().parents[1]
NOTES_FILE = ROOT / "ios/appstore/review-notes.txt"
WHATS_NEW_FILE = ROOT / "ios/appstore/whats-new-fr.txt"
LOCALE = "fr-FR"
EDITABLE = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED", "INVALID_BINARY"}
NOTES_MAX = 4000          # limite d'Apple pour les notes de revue
WHATS_NEW_MAX = 4000
BUILD_WAIT_S, POLL_S = 45 * 60, 30
PUBLISHED = {"READY_FOR_SALE", "READY_FOR_DISTRIBUTION", "REPLACED_WITH_NEW_VERSION", "REMOVED_FROM_SALE",
             "DEVELOPER_REMOVED_FROM_SALE"}


class Asc:
    def __init__(self, key: str) -> None:
        self.key = key

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        out = api(self.key, method, path, body)
        if "error" in out:
            raise SystemExit(f"App Store Connect {method} {path} : HTTP {out['error']} {out['detail']}")
        return out

    def data(self, path: str) -> list:
        return self.call("GET", path).get("data") or []


def pick_app(apps: list) -> str:
    """L'app de l'App Store, jamais la BETA : le filtre d'Apple renvoie aussi ch.bobycharbon.party.beta."""
    exact = [a for a in apps if a.get("attributes", {}).get("bundleId") == BUNDLE_ID]
    if len(exact) != 1:
        raise SystemExit(f"App {BUNDLE_ID} introuvable ou ambiguë ({len(exact)} résultats exacts)")
    return exact[0]["id"]


def app_id(asc: Asc) -> str:
    return pick_app(asc.data(f"/v1/apps?filter[bundleId]={BUNDLE_ID}"))


def versions(asc: Asc, app: str) -> list:
    return asc.data(f"/v1/apps/{app}/appStoreVersions?filter[platform]=IOS&limit=10")


def review_detail(asc: Asc, version_id: str) -> dict | None:
    out = api(asc.key, "GET", f"/v1/appStoreVersions/{version_id}/appStoreReviewDetail")
    return out.get("data") if "error" not in out else None


def state(v: dict) -> str:
    return v["attributes"].get("appVersionState") or v["attributes"].get("appStoreState") or ""


def check(key: str) -> int:
    asc = Asc(key)
    app = app_id(asc)
    print(f"App {BUNDLE_ID} : {app}")
    for v in versions(asc, app):
        a = v["attributes"]
        print(f"- version {a['versionString']} : {state(v)} (créée {a.get('createdDate', '')[:10]})")
        detail = review_detail(asc, v["id"])
        if detail:
            d = detail["attributes"]
            demo = f"oui ({d['demoAccountName']})" if d.get("demoAccountName") else "non"
            print(f"  revue : compte de démo {demo}, connexion requise {d.get('demoAccountRequired')}, "
                  f"contact {d.get('contactEmail') or '—'}, notes {len(d.get('notes') or '')} caractères")
        for loc in asc.data(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations"):
            la = loc["attributes"]
            print(f"  {la['locale']} : nouveautés {len(la.get('whatsNew') or '')} car., "
                  f"description {len(la.get('description') or '')} car.")
        for loc in asc.data(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations"):
            la = loc["attributes"]
            print(f"  fiche {la['locale']} : support {la.get('supportUrl')}, marketing {la.get('marketingUrl')}, "
                  f"mots-clés {la.get('keywords')!r}\n  description : {la.get('description')!r}")
        rating = api(asc.key, "GET", f"/v1/appStoreVersions/{v['id']}/ageRatingDeclaration")
        if "error" not in rating:
            print(f"  âge : {rating['data']['attributes']}")
    for info in asc.data(f"/v1/apps/{app}/appInfos"):
        print(f"- appInfo {info['id']} : {info['attributes'].get('appStoreState') or info['attributes'].get('state')}, "
              f"âge {info['attributes'].get('appStoreAgeRating')}")
        for loc in asc.data(f"/v1/appInfos/{info['id']}/appInfoLocalizations"):
            la = loc["attributes"]
            print(f"  {la['locale']} : nom {la.get('name')!r}, sous-titre {la.get('subtitle')!r}, "
                  f"confidentialité {la.get('privacyPolicyUrl')}")
        rating = api(asc.key, "GET", f"/v1/appInfos/{info['id']}/ageRatingDeclaration")
        if "error" not in rating:
            print(f"  âge (appInfo) : {rating['data']['attributes']}")
    for b in asc.data(f"/v1/builds?filter[app]={app}&filter[preReleaseVersion.platform]=IOS&sort=-uploadedDate&limit=5"):
        a = b["attributes"]
        print(f"- build {a['version']} : {a['processingState']}, envoyé {a['uploadedDate'][:16]}, expiré {a.get('expired')}")
    details(asc, app)
    return 0


def masked(value: str | None) -> str:
    return "—" if not value else f"oui (…{value[-2:]})"


def details(asc: Asc, app: str) -> None:
    """Le reste de la fiche, en lecture : droits, catégories, version, contact (masqué), disponibilité, prix, captures."""
    a = asc.call("GET", f"/v1/apps/{app}")["data"]["attributes"]
    print(f"- app : droits de contenu {a.get('contentRightsDeclaration')}, langue {a.get('primaryLocale')}")
    for info in asc.data(f"/v1/apps/{app}/appInfos"):
        for rel in ("primaryCategory", "primarySubcategoryOne", "secondaryCategory"):
            out = api(asc.key, "GET", f"/v1/appInfos/{info['id']}/{rel}")
            print(f"  {rel} : {(out.get('data') or {}).get('id') if 'error' not in out else out['error']}")
    for v in versions(asc, app):
        va = v["attributes"]
        print(f"- version {va['versionString']} : copyright {va.get('copyright')!r}, sortie {va.get('releaseType')}")
        detail = review_detail(asc, v["id"])
        if detail:
            d = detail["attributes"]
            print(f"  contact : prénom {masked(d.get('contactFirstName'))}, nom {masked(d.get('contactLastName'))}, "
                  f"téléphone {masked(d.get('contactPhone'))}, e-mail {d.get('contactEmail')}, "
                  f"code de démo {'saisi' if d.get('demoAccountPassword') else 'MANQUANT'}")
        for loc in asc.data(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations"):
            for s in asc.data(f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets"):
                shots = asc.data(f"/v1/appScreenshotSets/{s['id']}/appScreenshots")
                print(f"  captures {s['attributes']['screenshotDisplayType']} : {len(shots)}")
                for shot in shots:
                    asset = shot["attributes"].get("imageAsset") or {}
                    url = (asset.get("templateUrl") or "").replace("{w}", "600").replace("{h}", "1300").replace("{f}", "png")
                    print(f"    {shot['attributes'].get('fileName')} {url}")
            for s in asc.data(f"/v1/appStoreVersionLocalizations/{loc['id']}/appPreviewSets"):
                previews = asc.data(f"/v1/appPreviewSets/{s['id']}/appPreviews")
                print(f"  aperçus vidéo {s['attributes'].get('previewType')} : {len(previews)}")
                for preview in previews:
                    print(f"    {preview['attributes'].get('fileName')}")
    avail = api(asc.key, "GET", f"/v1/apps/{app}/appAvailabilityV2")
    if "error" not in avail:
        terr = asc.data(f"/v2/appAvailabilities/{avail['data']['id']}/territoryAvailabilities?limit=200&include=territory")
        on = sorted(t["relationships"]["territory"]["data"]["id"] for t in terr if t["attributes"].get("available"))
        off = sorted(t["relationships"]["territory"]["data"]["id"] for t in terr if not t["attributes"].get("available"))
        print(f"- disponible dans {len(on)} pays : {', '.join(on)}")
        print(f"- non disponible ({len(off)}) : {', '.join(off)}")
    else:
        print(f"- disponibilité : {avail['error']} {str(avail['detail'])[:200]}")
    price = api(asc.key, "GET", f"/v1/apps/{app}/appPriceSchedule?include=baseTerritory,manualPrices")
    if "error" not in price:
        print(f"- prix : {[i.get('type') + ':' + i.get('id', '')[:40] for i in price.get('included', [])]}")
    else:
        print(f"- prix : {price['error']} {str(price['detail'])[:200]}")


def editable_version(asc: Asc, app: str, version: str) -> dict:
    for v in versions(asc, app):
        if v["attributes"]["versionString"] == version and state(v) in EDITABLE:
            return v
    created = asc.call("POST", "/v1/appStoreVersions", {"data": {
        "type": "appStoreVersions", "attributes": {"platform": "IOS", "versionString": version},
        "relationships": {"app": {"data": {"type": "apps", "id": app}}}}})
    print(f"Version {version} créée")
    return created["data"]


def processed_build(asc: Asc, app: str, build: str) -> dict:
    deadline = time.time() + BUILD_WAIT_S
    while time.time() < deadline:
        found = asc.data(f"/v1/builds?filter[app]={app}&filter[version]={build}&filter[preReleaseVersion.platform]=IOS&limit=1")
        if found and found[0]["attributes"]["processingState"] == "VALID":
            return found[0]
        if found and found[0]["attributes"]["processingState"] in ("FAILED", "INVALID"):
            raise SystemExit(f"Build {build} refusé au traitement par Apple")
        print(f"Build {build} : traitement Apple en cours…")
        time.sleep(POLL_S)
    raise SystemExit(f"Build {build} pas traité au bout de {BUILD_WAIT_S // 60} min")


def known_demo(asc: Asc, app: str, current: dict | None) -> dict:
    """Compte de démo déjà saisi (cette version, sinon la précédente) : il n'est jamais écrit dans le dépôt."""
    if current and current["attributes"].get("demoAccountName"):
        return current["attributes"]
    for v in versions(asc, app):
        detail = review_detail(asc, v["id"])
        if detail and detail["attributes"].get("demoAccountName"):
            return detail["attributes"]
    return {}


def save_review_detail(asc: Asc, version_id: str, current: dict | None, attrs: dict) -> None:
    if current:
        asc.call("PATCH", f"/v1/appStoreReviewDetails/{current['id']}", {"data": {
            "type": "appStoreReviewDetails", "id": current["id"], "attributes": attrs}})
        return
    asc.call("POST", "/v1/appStoreReviewDetails", {"data": {
        "type": "appStoreReviewDetails", "attributes": attrs,
        "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": version_id}}}}})


def send_to_review(asc: Asc, app: str, version_id: str) -> str:
    sub = asc.call("POST", "/v1/reviewSubmissions", {"data": {
        "type": "reviewSubmissions", "attributes": {"platform": "IOS"},
        "relationships": {"app": {"data": {"type": "apps", "id": app}}}}})["data"]
    asc.call("POST", "/v1/reviewSubmissionItems", {"data": {
        "type": "reviewSubmissionItems",
        "relationships": {"reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sub["id"]}},
                          "appStoreVersion": {"data": {"type": "appStoreVersions", "id": version_id}}}}})
    done = asc.call("PATCH", f"/v1/reviewSubmissions/{sub['id']}", {"data": {
        "type": "reviewSubmissions", "id": sub["id"], "attributes": {"submitted": True}}})
    return done["data"]["attributes"].get("state", "")


def submit(key: str, version: str, build: str) -> int:
    notes = NOTES_FILE.read_text().strip()
    if not notes or len(notes) > NOTES_MAX:
        raise SystemExit(f"Notes de revue vides ou trop longues ({len(notes)} / {NOTES_MAX})")
    asc = Asc(key)
    app = app_id(asc)
    first_release = not any(state(x) in PUBLISHED for x in versions(asc, app))
    whats_new = "" if first_release else WHATS_NEW_FILE.read_text().strip()
    if not first_release and (not whats_new or len(whats_new) > WHATS_NEW_MAX):
        raise SystemExit(f"Nouveautés vides ou trop longues ({len(whats_new)} / {WHATS_NEW_MAX})")
    v = editable_version(asc, app, version)
    current = review_detail(asc, v["id"])
    demo = known_demo(asc, app, current)
    if not demo.get("demoAccountName") or not demo.get("demoAccountPassword"):
        raise SystemExit("Aucun compte de démo connu : à saisir une fois dans App Store Connect (jamais dans le dépôt)")

    b = processed_build(asc, app, build)
    if b["attributes"].get("usesNonExemptEncryption") is None:
        asc.call("PATCH", f"/v1/builds/{b['id']}", {"data": {"type": "builds", "id": b["id"],
                                                             "attributes": {"usesNonExemptEncryption": False}}})
    asc.call("PATCH", f"/v1/appStoreVersions/{v['id']}/relationships/build", {"data": {"type": "builds", "id": b["id"]}})
    print(f"Build {build} choisi pour la version {version}")

    if first_release:
        print("Première version : pas de « Nouveautés » (Apple les refuse)")
    else:
        loc = next((x for x in asc.data(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations")
                    if x["attributes"]["locale"] == LOCALE), None)
        if loc is None:
            raise SystemExit(f"Pas de fiche {LOCALE} pour la version {version}")
        asc.call("PATCH", f"/v1/appStoreVersionLocalizations/{loc['id']}", {"data": {
            "type": "appStoreVersionLocalizations", "id": loc["id"], "attributes": {"whatsNew": whats_new}}})
        print("Nouveautés enregistrées")

    attrs = {"notes": notes, "demoAccountRequired": True, "demoAccountName": demo["demoAccountName"],
             "demoAccountPassword": demo["demoAccountPassword"]}
    attrs.update({k: demo[k] for k in ("contactFirstName", "contactLastName", "contactPhone", "contactEmail") if demo.get(k)})
    save_review_detail(asc, v["id"], current, attrs)
    print(f"Notes pour les examinateurs ({len(notes)} car.) et compte de démo enregistrés")

    print(f"Version {version} (build {build}) envoyée en revue : {send_to_review(asc, app, v['id'])}")
    return 0


METADATA_FILE = ROOT / "ios/appstore/metadata-fr.json"


def patch(asc: Asc, kind: str, obj_id: str, attrs: dict, label: str) -> None:
    out = api(asc.key, "PATCH", f"/v1/{kind}/{obj_id}", {"data": {"type": kind, "id": obj_id, "attributes": attrs}})
    print(f"{label} : {'refusé, ' + str(out['error']) + ' ' + str(out['detail'])[:400] if 'error' in out else 'enregistré'}")


def fill(key: str, version: str) -> int:
    """Fiche de la version (nom, sous-titre, description, URL, mots-clés), classification par âge et nom du compte de
    démo, d'après ios/appstore/metadata-fr.json. Le code du compte de démo n'est jamais écrit ici (saisi à la main)."""
    meta = json.loads(METADATA_FILE.read_text())
    asc = Asc(key)
    app = app_id(asc)
    v = editable_version(asc, app, version)
    for info in asc.data(f"/v1/apps/{app}/appInfos"):
        if (info["attributes"].get("appStoreState") or info["attributes"].get("state")) not in EDITABLE:
            continue
        for loc in asc.data(f"/v1/appInfos/{info['id']}/appInfoLocalizations"):
            if loc["attributes"]["locale"] == LOCALE:
                patch(asc, "appInfoLocalizations", loc["id"], {"name": meta["name"]}, f"Nom « {meta['name']} »")
                patch(asc, "appInfoLocalizations", loc["id"], {"subtitle": meta["subtitle"],
                      "privacyPolicyUrl": meta["privacyPolicyUrl"]}, "Sous-titre et confidentialité")
        rating = api(asc.key, "GET", f"/v1/appInfos/{info['id']}/ageRatingDeclaration")
        if "error" not in rating:
            patch(asc, "ageRatingDeclarations", rating["data"]["id"], meta["ageRating"], "Classification par âge")
    for loc in asc.data(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations"):
        if loc["attributes"]["locale"] == LOCALE:
            # URL vide (marketingUrl, refus 1.4.3 : jamais vers le site et ses jeux) : effacée (null), pas une chaîne vide.
            patch(asc, "appStoreVersionLocalizations", loc["id"], {k: meta[k] or None for k in
                  ("description", "keywords", "supportUrl", "marketingUrl")}, "Description, mots-clés et URL")
    current = review_detail(asc, v["id"])
    attrs = {"demoAccountRequired": True, "demoAccountName": meta["demoAccountName"]}
    if current:
        patch(asc, "appStoreReviewDetails", current["id"], attrs, "Compte de démo (nom ; code à saisir à la main)")
    else:
        save_review_detail(asc, v["id"], None, attrs)
        print("Compte de démo (nom) créé ; code à saisir à la main")
    return 0


SCREENSHOTS_DIR = ROOT / "ios/appstore/screenshots"
SCREENSHOT_TYPE = "APP_IPHONE_67"          # 6,9" / 6,7" : 1320 × 2868, la taille exigée par Apple pour l'iPhone
DUO_SCREENSHOTS_DIR = ROOT / "ios/appstore/screenshots-duo"
DUO_SCREENSHOT_TYPE = "APP_IPHONE_DUO"     # iPhone Duo, écran extérieur : 1398 × 2034 (type lu sur la fiche en ligne)
IPHONE_TYPES = {"APP_IPHONE_67", "APP_IPHONE_65", "APP_IPHONE_61", "APP_IPHONE_58", "APP_IPHONE_55"}
ASSET_WAIT_S = 5 * 60


def upload_parts(operations: list, data: bytes) -> None:
    for op in operations:
        chunk = data[op["offset"]:op["offset"] + op["length"]]
        headers = {h["name"]: h["value"] for h in op.get("requestHeaders") or []}
        req = urllib.request.Request(op["url"], data=chunk, method=op["method"], headers=headers)
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()


def upload_screenshot(asc: Asc, set_id: str, path: pathlib.Path) -> str:
    data = path.read_bytes()
    reserved = asc.call("POST", "/v1/appScreenshots", {"data": {
        "type": "appScreenshots", "attributes": {"fileName": path.name, "fileSize": len(data)},
        "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": set_id}}}}})["data"]
    upload_parts(reserved["attributes"]["uploadOperations"], data)
    asc.call("PATCH", f"/v1/appScreenshots/{reserved['id']}", {"data": {
        "type": "appScreenshots", "id": reserved["id"],
        "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
    return reserved["id"]


def wait_assets(asc: Asc, ids: list[str]) -> None:
    deadline = time.time() + ASSET_WAIT_S
    pending = set(ids)
    while pending and time.time() < deadline:
        for shot_id in sorted(pending):
            st = asc.call("GET", f"/v1/appScreenshots/{shot_id}")["data"]["attributes"].get("assetDeliveryState") or {}
            if st.get("state") == "COMPLETE":
                pending.discard(shot_id)
            elif st.get("state") == "FAILED":
                raise SystemExit(f"Capture refusée par Apple : {st.get('errors')}")
        if pending:
            time.sleep(10)
    if pending:
        raise SystemExit(f"Captures pas traitées au bout de {ASSET_WAIT_S // 60} min : {sorted(pending)}")


def shot_files(folder: pathlib.Path, required: bool) -> list[pathlib.Path]:
    """Captures d'un dossier, dans l'ordre des noms : 3 à 10 (Apple), ou aucune pour un jeu facultatif."""
    files = sorted(folder.glob("*.png"))
    if (files or required) and not 3 <= len(files) <= 10:
        raise SystemExit(f"Il faut 3 à 10 captures dans {folder} ({len(files)} trouvées)")
    return files


def replace_set(asc: Asc, loc_id: str, display_type: str, files: list[pathlib.Path]) -> list[str]:
    """Le jeu `display_type` de la fiche ne contient plus que `files` : les anciennes captures partent AVANT l'envoi
    (Apple n'en garde que 10 par jeu ; la version est modifiable, rien n'est en ligne)."""
    sets = asc.data(f"/v1/appStoreVersionLocalizations/{loc_id}/appScreenshotSets")
    target = next((s for s in sets if s["attributes"]["screenshotDisplayType"] == display_type), None)
    if target is None:
        target = asc.call("POST", "/v1/appScreenshotSets", {"data": {
            "type": "appScreenshotSets", "attributes": {"screenshotDisplayType": display_type},
            "relationships": {"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations",
                                                                        "id": loc_id}}}}})["data"]
        print(f"Jeu de captures {display_type} créé")
    for shot in asc.data(f"/v1/appScreenshotSets/{target['id']}/appScreenshots"):
        asc.call("DELETE", f"/v1/appScreenshots/{shot['id']}")
        print(f"Ancienne capture retirée : {display_type} {shot['attributes'].get('fileName')}")
    ids = [upload_screenshot(asc, target["id"], f) for f in files]
    wait_assets(asc, ids)
    print(f"{len(ids)} captures {display_type} envoyées : {', '.join(f.name for f in files)}")
    return ids


def screens(key: str, version: str) -> int:
    """Remplace les captures de la fiche fr-FR : iPhone 6,9" par ios/appstore/screenshots/*.png, iPhone Duo par
    ios/appstore/screenshots-duo/*.png (ordre des noms), retire les autres tailles d'iPhone et les aperçus vidéo."""
    files = shot_files(SCREENSHOTS_DIR, required=True)
    duo = shot_files(DUO_SCREENSHOTS_DIR, required=False)
    asc = Asc(key)
    app = app_id(asc)
    v = editable_version(asc, app, version)
    loc = next((x for x in asc.data(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations")
                if x["attributes"]["locale"] == LOCALE), None)
    if loc is None:
        raise SystemExit(f"Pas de fiche {LOCALE}")
    replace_set(asc, loc["id"], SCREENSHOT_TYPE, files)
    if duo:
        replace_set(asc, loc["id"], DUO_SCREENSHOT_TYPE, duo)
    # Les captures des autres tailles d'iPhone partent : sinon l'App Store montrerait encore l'ancienne app sur les
    # petits écrans.
    for s in asc.data(f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets"):
        if s["attributes"]["screenshotDisplayType"] not in IPHONE_TYPES - {SCREENSHOT_TYPE}:
            continue
        for shot in asc.data(f"/v1/appScreenshotSets/{s['id']}/appScreenshots"):
            asc.call("DELETE", f"/v1/appScreenshots/{shot['id']}")
            print(f"Ancienne capture retirée : {s['attributes']['screenshotDisplayType']} "
                  f"{shot['attributes'].get('fileName')}")
    # Aperçus vidéo (App Previews) : tous retirés, de chaque taille (l'ancien tour de l'app montrait l'onglet Musique).
    for s in asc.data(f"/v1/appStoreVersionLocalizations/{loc['id']}/appPreviewSets"):
        for preview in asc.data(f"/v1/appPreviewSets/{s['id']}/appPreviews"):
            asc.call("DELETE", f"/v1/appPreviews/{preview['id']}")
            print(f"Aperçu vidéo retiré : {s['attributes'].get('previewType')} {preview['attributes'].get('fileName')}")
    return 0


GUIDE_FILE = ROOT / "docs/app-store/guide-revue-apple.pdf"


def attach(key: str, version: str) -> int:
    """Pièce jointe de la revue (App Review Information › Attachment) : remplace les anciennes par le guide PDF."""
    data = GUIDE_FILE.read_bytes()
    asc = Asc(key)
    v = editable_version(asc, app_id(asc), version)
    detail = review_detail(asc, v["id"])
    if detail is None:
        raise SystemExit("Pas encore d'informations de revue pour cette version (lancer fill d'abord)")
    for old in asc.data(f"/v1/appStoreReviewDetails/{detail['id']}/appStoreReviewAttachments"):
        asc.call("DELETE", f"/v1/appStoreReviewAttachments/{old['id']}")
        print(f"Ancienne pièce jointe retirée : {old['attributes'].get('fileName')}")
    reserved = asc.call("POST", "/v1/appStoreReviewAttachments", {"data": {
        "type": "appStoreReviewAttachments", "attributes": {"fileName": GUIDE_FILE.name, "fileSize": len(data)},
        "relationships": {"appStoreReviewDetail": {"data": {"type": "appStoreReviewDetails", "id": detail["id"]}}}}})["data"]
    upload_parts(reserved["attributes"]["uploadOperations"], data)
    asc.call("PATCH", f"/v1/appStoreReviewAttachments/{reserved['id']}", {"data": {
        "type": "appStoreReviewAttachments", "id": reserved["id"],
        "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
    deadline = time.time() + ASSET_WAIT_S
    while time.time() < deadline:
        st = asc.call("GET", f"/v1/appStoreReviewAttachments/{reserved['id']}")["data"]["attributes"]
        state_ = (st.get("assetDeliveryState") or {}).get("state")
        if state_ in ("COMPLETE", "FAILED"):
            break
        time.sleep(10)
    print(f"Pièce jointe {GUIDE_FILE.name} ({len(data) // 1024} Ko) : {state_}")
    return 0 if state_ == "COMPLETE" else 1


def cancel(key: str) -> int:
    """Retire de la revue l'envoi en attente (WAITING_FOR_REVIEW), avant qu'Apple commence : sans pénalité."""
    asc = Asc(key)
    app = app_id(asc)
    subs = asc.data(f"/v1/reviewSubmissions?filter[app]={app}&filter[platform]=IOS&limit=20")
    waiting = [s for s in subs if s["attributes"].get("state") in ("WAITING_FOR_REVIEW", "READY_FOR_REVIEW")]
    if not waiting:
        print("Aucun envoi en attente : " + ", ".join(s["attributes"].get("state", "?") for s in subs))
        return 1
    for s in waiting:
        done = asc.call("PATCH", f"/v1/reviewSubmissions/{s['id']}", {"data": {
            "type": "reviewSubmissions", "id": s["id"], "attributes": {"canceled": True}}})
        print(f"Envoi {s['id']} retiré de la revue : {done['data']['attributes'].get('state', '')}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "attach":
        sys.exit(attach(sys.argv[2], sys.argv[3]))
    if len(sys.argv) == 4 and sys.argv[1] == "fill":
        sys.exit(fill(sys.argv[2], sys.argv[3]))
    if len(sys.argv) == 4 and sys.argv[1] == "screens":
        sys.exit(screens(sys.argv[2], sys.argv[3]))
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "cancel" and len(sys.argv) == 3:
        sys.exit(cancel(sys.argv[2]))
    if mode == "check" and len(sys.argv) == 3:
        sys.exit(check(sys.argv[2]))
    if mode == "submit" and len(sys.argv) == 5:
        sys.exit(submit(*sys.argv[2:5]))
    sys.exit(__doc__)
