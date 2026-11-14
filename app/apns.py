"""Notifications natives de l'app iOS (ios/) via APNs : HTTP/2 vers Apple, jeton d'authentification ES256.

Une WKWebView n'a pas Web Push : l'app inscrit l'appareil auprès d'Apple et le site l'abonne sous la forme
{"endpoint": "apns:<jeton>", "apns": {"token", "environment", "topic"}} (même stockage que Web Push).
Clé APNs (.p8, developer.apple.com › Keys) : variables APNS_KEY_P8 (contenu) et APNS_KEY_ID ; sans elles,
les abonnements natifs sont gardés mais rien n'est envoyé."""
import base64
import logging
import json
import threading
import time
import uuid

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

HOSTS = {"production": "https://api.push.apple.com", "sandbox": "https://api.sandbox.push.apple.com"}
# Seules nos apps : VendrediParty (App Store) et VendrediPartyBETA (TestFlight).
TOPICS = ("ch.bobycharbon.party", "ch.bobycharbon.party.beta")
TEAM_ID = "GS2B6GA9JA"
# Apple refuse un jeton de plus d'une heure et un renouvellement plus d'une fois toutes les 20 minutes.
TOKEN_LIFETIME = 50 * 60
# L'appareil a désinstallé l'app ou appartient à une autre app : on oublie l'abonnement.
GONE_REASONS = {"Unregistered", "BadDeviceToken", "DeviceTokenNotForTopic"}
TTL_SECONDS = 300
# Apple surchargée (429 TooManyRequests, 500, 503) ou injoignable : deux nouveaux essais, après 1 puis 3 s.
RETRY_STATUSES = {429, 500, 503}
RETRY_DELAYS = (1, 3)
TOKEN_HEX = set("0123456789abcdef")


def is_device_token(token) -> bool:
    return isinstance(token, str) and 64 <= len(token) <= 200 and set(token) <= TOKEN_HEX


def pem(raw: str) -> str:
    """Clé .p8 telle que collée dans une variable d'environnement : multiligne, sur une seule ligne (Dockhand),
    avec des « \\n » littéraux ou sans en-têtes → PEM valide."""
    body = "".join(raw.replace("\\n", "\n").replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").split())
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"


def _b64(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


class Apns:
    def __init__(self, key_pem: str, key_id: str, team_id: str = TEAM_ID, client: httpx.Client | None = None):
        self.key = serialization.load_pem_private_key(pem(key_pem).encode(), None)
        self.key_id, self.team_id = key_id, team_id
        self.client = client or httpx.Client(http2=True, timeout=10)
        self._token, self._token_at = "", 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, env) -> "Apns | None":
        key, key_id = env.get("APNS_KEY_P8"), env.get("APNS_KEY_ID")
        if not key or not key_id:
            return None
        try:
            return cls(key, key_id, env.get("APNS_TEAM_ID") or TEAM_ID)
        except ValueError:
            # Clé mal collée : le site doit démarrer quand même (sans notifications natives), jamais planter.
            logging.getLogger(__name__).error("APNS_KEY_P8 illisible : notifications natives désactivées")
            return None

    def _provider_token(self) -> str:
        with self._lock:
            if not self._token or time.time() - self._token_at > TOKEN_LIFETIME:
                head = _b64(json.dumps({"alg": "ES256", "kid": self.key_id}).encode())
                now = int(time.time())
                claims = _b64(json.dumps({"iss": self.team_id, "iat": now}).encode())
                r, s = decode_dss_signature(self.key.sign(head + b"." + claims, ec.ECDSA(hashes.SHA256())))
                signature = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
                self._token, self._token_at = (head + b"." + claims + b"." + signature).decode(), now
            return self._token

    def send(self, sub: dict, payload: dict) -> bool:
        """Envoie une notification ; False si l'appareil n'existe plus pour cette app (abonnement à oublier)."""
        target = sub["apns"]
        silent = payload.get("silent") is True
        # Pause des notifications (lune des Réglages) : livrée sans son ni vibration, sans allumer l'écran.
        aps = {"alert": {"title": payload.get("title", ""), "body": payload.get("body", "")},
               **({"interruption-level": "passive"} if silent else {"sound": "default"})}
        if payload.get("tag"):
            aps["thread-id"] = payload["tag"]  # les notifications d'un même sujet se regroupent
        body = {"aps": aps}
        if payload.get("url"):
            body["url"] = payload["url"]  # ouverte par l'app au toucher (PushRegistrar.swift)
        return self._post(target, body, {"apns-topic": target["topic"], "apns-push-type": "alert",
                                         "apns-priority": "5" if silent else "10"})

    def send_live_activity(self, target: dict, event: str, aps: dict, priority: int = 10) -> bool:
        """Live Activity (app/live_activity.py) : event start | update | end ; target = jeton de l'activité ou de
        démarrage, environnement et app. False si le jeton n'existe plus (activité terminée, app désinstallée)."""
        body = {"aps": {"timestamp": int(time.time()), "event": event, **aps}}
        return self._post(target, body, {"apns-topic": target["topic"] + ".push-type.liveactivity",
                                         "apns-push-type": "liveactivity", "apns-priority": str(priority)})

    def _post(self, target: dict, body: dict, headers: dict) -> bool:
        """Envoi avec nouveaux essais. Même apns-id et apns-collapse-id à chaque essai : une alerte arrivée malgré une
        erreur réseau est remplacée sur l'iPhone par la suivante, jamais montrée deux fois (Live Activity : iOS ignore
        déjà une mise à jour au même « timestamp »)."""
        notification_id = str(uuid.uuid4())
        headers = {**headers, "apns-id": notification_id, "apns-expiration": str(int(time.time()) + TTL_SECONDS)}
        if headers["apns-push-type"] == "alert":
            headers["apns-collapse-id"] = notification_id
        response = None
        for delay in (*RETRY_DELAYS, None):
            try:
                response = self.client.post(f"{HOSTS[target['environment']]}/3/device/{target['token']}", json=body,
                                            headers={**headers, "authorization": f"bearer {self._provider_token()}"})
            except httpx.TransportError:
                response = None
            else:
                if response.status_code == 403 and self._reason(response) == "ExpiredProviderToken":
                    with self._lock:
                        self._token = ""  # horloge décalée ou jeton trop vieux : un nouveau au prochain essai
                elif response.status_code not in RETRY_STATUSES:
                    break
            if delay is None:
                break
            time.sleep(delay)
        return response is None or self._alive(response)

    @staticmethod
    def _reason(response: httpx.Response) -> str:
        try:
            return response.json().get("reason") or ""
        except (ValueError, AttributeError):
            return ""

    @staticmethod
    def _alive(response: httpx.Response) -> bool:
        return response.status_code != 410 and (response.status_code != 400 or Apns._reason(response) not in GONE_REASONS)
