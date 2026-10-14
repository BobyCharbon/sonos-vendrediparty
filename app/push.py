"""Notifications push (Web Push) : « ton titre passe » pour les invités, nouveaux messages pour l'hôte."""

import base64
import json
import threading
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

# Le serveur envoie une requête à l'adresse fournie par le téléphone : seulement les services push connus.
PUSH_HOSTS = ("fcm.googleapis.com", "push.services.mozilla.com", "push.apple.com", "notify.windows.com")


def valid_subscription(sub: dict) -> bool:
    try:
        url = urlparse(sub["endpoint"])
        keys = sub["keys"]
        ok_host = any(url.hostname == h or url.hostname.endswith("." + h) for h in PUSH_HOSTS)
        return (url.scheme == "https" and ok_host and len(sub["endpoint"]) < 1000
                and isinstance(keys["p256dh"], str) and isinstance(keys["auth"], str))
    except (KeyError, TypeError, AttributeError):
        return False


class Push:
    def __init__(self, data_dir: Path, subject: str):
        self.subject = subject
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
                try:
                    webpush(sub, json.dumps(payload), vapid_private_key=self.vapid,
                            vapid_claims={"sub": self.subject}, ttl=300, timeout=10)
                except WebPushException as e:
                    if e.response is not None and e.response.status_code in (404, 410):
                        on_gone(sub)
                except Exception:
                    pass  # service push injoignable : tant pis pour cette notification
        threading.Thread(target=run, daemon=True).start()
