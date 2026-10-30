#!/usr/bin/env python3
"""Publie une BETA envoyée à TestFlight dans le groupe public « Invités » (lien public), dès qu'Apple l'a traitée.

Lancé par .github/workflows/ios-testflight.yml après l'envoi (develop seulement) :
  python3 tools/testflight_publish.py <identifiant de l'app> <numéro de build> <fichier .p8> [IOS|TV_OS]
Variables : ASC_KEY_ID, ASC_ISSUER_ID (clé API App Store Connect). Attend le traitement (30 min au plus), déclare
la conformité export (pas de chiffrement propre), ajoute le build au groupe et le soumet à la vérification bêta.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

API = "https://api.appstoreconnect.apple.com"
GROUP_NAME = "Invités"
WAIT_S, POLL_S = 30 * 60, 30
ADD_TRIES = 10  # ajout au groupe : 5 minutes au plus
ALREADY_SUBMITTED = {"WAITING_FOR_BETA_REVIEW", "IN_BETA_REVIEW", "BETA_APPROVED", "IN_BETA_TESTING"}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def token(key_path: str) -> str:
    key = serialization.load_pem_private_key(open(key_path, "rb").read(), None)
    head = b64(json.dumps({"alg": "ES256", "kid": os.environ["ASC_KEY_ID"], "typ": "JWT"}).encode())
    now = int(time.time())
    body = b64(json.dumps({"iss": os.environ["ASC_ISSUER_ID"], "iat": now, "exp": now + 1100,
                           "aud": "appstoreconnect-v1"}).encode())
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def api(key_path: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token(key_path)}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:500]}


def main(app_id: str, version: str, key_path: str, platform: str = "IOS") -> int:
    deadline = time.time() + WAIT_S
    build = None
    while time.time() < deadline:
        # iPhone et Apple TV portent le même numéro de build : la plateforme les distingue.
        found = api(key_path, "GET", f"/v1/builds?filter[app]={app_id}&filter[version]={version}"
                                     f"&filter[preReleaseVersion.platform]={platform}&limit=1").get("data") or []
        if found and found[0]["attributes"]["processingState"] == "VALID":
            build = found[0]
            break
        if found and found[0]["attributes"]["processingState"] in ("FAILED", "INVALID"):
            print(f"Build {version} refusé au traitement par Apple")
            return 1
        print(f"Build {version} : traitement Apple en cours…")
        time.sleep(POLL_S)
    if build is None:
        print(f"Build {version} pas encore traité au bout de {WAIT_S // 60} min : à publier à la main")
        return 1
    bid = build["id"]
    if build["attributes"].get("usesNonExemptEncryption") is None:
        api(key_path, "PATCH", f"/v1/builds/{bid}",
            {"data": {"type": "builds", "id": bid, "attributes": {"usesNonExemptEncryption": False}}})
    groups = api(key_path, "GET", f"/v1/apps/{app_id}/betaGroups").get("data") or []
    group = next((g for g in groups if g["attributes"]["name"] == GROUP_NAME), None)
    if group is None:
        print(f"Groupe « {GROUP_NAME} » introuvable")
        return 1
    # Juste après le traitement, Apple répond parfois « build introuvable » (404) quelques minutes : on réessaie.
    for attempt in range(ADD_TRIES):
        added = api(key_path, "POST", f"/v1/betaGroups/{group['id']}/relationships/builds",
                    {"data": [{"type": "builds", "id": bid}]})
        if added.get("error") != 404:
            break
        print(f"Build {version} pas encore visible pour le groupe : nouvel essai dans {POLL_S} s")
        time.sleep(POLL_S)
    if "error" in added:
        print("Ajout au groupe refusé :", added["detail"])
        return 1
    details = api(key_path, "GET", f"/v1/buildBetaDetails?filter[build]={bid}").get("data") or [{}]
    state = details[0].get("attributes", {}).get("externalBuildState", "")
    # Déjà soumis, en vérification ou déjà en test (relancé à la main) : rien à refaire.
    if state not in ALREADY_SUBMITTED:
        submitted = api(key_path, "POST", "/v1/betaAppReviewSubmissions",
                        {"data": {"type": "betaAppReviewSubmissions",
                                  "relationships": {"build": {"data": {"type": "builds", "id": bid}}}}})
        if "error" in submitted:
            print("Soumission à la vérification bêta refusée :", submitted["detail"])
            return 1
    print(f"Build {version} publié dans « {GROUP_NAME} » (lien public)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
