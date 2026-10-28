"""Notifications push : « ton titre passe » pour les invités, nouveaux messages pour l'hôte.
Web Push pour les navigateurs, APNs (app/apns.py) pour l'app iOS native."""

import base64
import json
import threading
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from . import apns

# Le serveur envoie une requête à l'adresse fournie par le téléphone : seulement les services push connus.
PUSH_HOSTS = ("fcm.googleapis.com", "push.services.mozilla.com", "push.apple.com", "notify.windows.com")


def valid_subscription(sub: dict) -> bool:
    if isinstance(sub, dict) and "apns" in sub:
        return valid_native_subscription(sub)
    try:
        url = urlparse(sub["endpoint"])
        keys = sub["keys"]
        ok_host = any(url.hostname == h or url.hostname.endswith("." + h) for h in PUSH_HOSTS)
        return (url.scheme == "https" and ok_host and len(sub["endpoint"]) < 1000
                and isinstance(keys["p256dh"], str) and isinstance(keys["auth"], str))
    except (KeyError, TypeError, AttributeError):
        return False


def valid_native_subscription(sub: dict) -> bool:
    """App iOS : {"endpoint": "apns:<jeton>", "apns": {"token", "environment", "topic"}}."""
    target = sub.get("apns")
    if not isinstance(target, dict):
        return False
    token = target.get("token")
    return (apns.is_device_token(token) and sub.get("endpoint") == f"apns:{token}"
            and target.get("environment") in apns.HOSTS and target.get("topic") in apns.TOPICS)


class Push:
    def __init__(self, data_dir: Path, subject: str, apns: "apns.Apns | None" = None):
        self.subject = subject
        self.apns = apns
        path = data_dir / "vapid.pem"
        if not path.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            vapid = Vapid()
            vapid.generate_keys()
            vapid.save_key(str(path))
        self.vapid = Vapid.from_file(str(path))
        raw = self.vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.public_key = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    def send(self, subs: list[dict], payload: dict, on_gone=lambda sub: None):
        """Envoie en arrière-plan ; on_gone(sub) quand l'abonnement n'existe plus (désinstallé, refusé)."""
        def run():
            for sub in subs:
                if "apns" in sub:
                    self._send_native(sub, payload, on_gone)
                    continue
                try:
                    webpush(sub, json.dumps(payload), vapid_private_key=self.vapid,
                            vapid_claims={"sub": self.subject}, ttl=300, timeout=10)
                except WebPushException as e:
                    if e.response is not None and e.response.status_code in (404, 410):
                        on_gone(sub)
                except Exception:
                    pass  # service push injoignable : tant pis pour cette notification
        threading.Thread(target=run, daemon=True).start()

    def _send_native(self, sub: dict, payload: dict, on_gone):
        if self.apns is None:
            return  # clé APNs pas encore configurée : l'abonnement reste pour plus tard
        try:
            if not self.apns.send(sub, payload):
                on_gone(sub)
        except Exception:
            pass  # Apple injoignable : tant pis pour cette notification

    def send_live_activity(self, target: dict, event: str, aps: dict, priority: int, on_gone=lambda: None):
        """Mise à jour d'une Live Activity en arrière-plan ; on_gone() si son jeton n'existe plus."""
        if self.apns is None:
            return
        def run():
            try:
                if not self.apns.send_live_activity(target, event, aps, priority):
                    on_gone()
            except Exception:
                pass  # Apple injoignable : la prochaine mise à jour rattrapera
        threading.Thread(target=run, daemon=True).start()
