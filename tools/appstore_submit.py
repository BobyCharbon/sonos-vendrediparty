#!/usr/bin/env python3
"""Envoi d'une version de l'app iPhone (App Store, ch.bobycharbon.party) à la revue d'Apple, par l'API App Store Connect.

Lancé par .github/workflows/ios-appstore.yml (secrets ASC_KEY_ID, ASC_ISSUER_ID, clé .p8) :
  python3 tools/appstore_submit.py check  <fichier .p8>
      lecture seule : versions, builds de l'app, notes et compte de démo de la revue (jamais le mot de passe).
  python3 tools/appstore_submit.py submit <fichier .p8> <version> <build>
      version modifiable (créée si besoin) ← build (traité, sans chiffrement propre), nouveautés
      (ios/appstore/whats-new-fr.txt, seulement après une 1re version publiée : Apple les refuse sur la première), notes pour les examinateurs (ios/appstore/review-notes.txt), compte de démo
      repris de la revue précédente (jamais dans le dépôt), puis envoi en revue.
Rien n'est envoyé si un fichier manque, si le build n'est pas traité ou si aucun compte de démo n'est connu.
"""
import json
import pathlib
import sys
import time

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


def app_id(asc: Asc) -> str:
    apps = asc.data(f"/v1/apps?filter[bundleId]={BUNDLE_ID}")
    if not apps:
        raise SystemExit(f"App {BUNDLE_ID} introuvable")
    return apps[0]["id"]


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
            patch(asc, "appStoreVersionLocalizations", loc["id"], {k: meta[k] for k in
                  ("description", "keywords", "supportUrl", "marketingUrl")}, "Description, mots-clés et URL")
    current = review_detail(asc, v["id"])
    attrs = {"demoAccountRequired": True, "demoAccountName": meta["demoAccountName"]}
    if current:
        patch(asc, "appStoreReviewDetails", current["id"], attrs, "Compte de démo (nom ; code à saisir à la main)")
    else:
        save_review_detail(asc, v["id"], None, attrs)
        print("Compte de démo (nom) créé ; code à saisir à la main")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "fill":
        sys.exit(fill(sys.argv[2], sys.argv[3]))
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "check" and len(sys.argv) == 3:
        sys.exit(check(sys.argv[2]))
    if mode == "submit" and len(sys.argv) == 5:
        sys.exit(submit(*sys.argv[2:5]))
    sys.exit(__doc__)
