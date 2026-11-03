"""Push APNs « vide » des billets Wallet : prévient chaque iPhone qu'un pass a changé (il redemande ensuite le pass
au serveur, PassKit Web Service). Pour les pass, Apple exige une connexion TLS avec le certificat du pass (pass.cer +
pass.key, sujet = pass.ch.bobycharbon.party.ticket), toujours sur la passerelle de production, corps « {} »."""
import logging
import ssl
import tempfile
import threading
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization

from .wallet import PASS_TYPE_ID, Signer

log = logging.getLogger(__name__)

GATEWAY = "https://api.push.apple.com"
# L'appareil a supprimé le pass ou le jeton n'est plus valable : Wallet se désinscrira lui-même.
GONE = {400, 410}
MAX_TOKENS = 500


def tls_context(folder: Path, signer: Signer) -> ssl.SSLContext:
    """Contexte TLS client avec le certificat du pass (DER converti en PEM dans un fichier temporaire, sans la clé)."""
    context = ssl.create_default_context()
    with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as cert_file:
        cert_file.write(signer.cert.public_bytes(serialization.Encoding.PEM))
    try:
        context.load_cert_chain(cert_file.name, folder / "pass.key")
    finally:
        Path(cert_file.name).unlink(missing_ok=True)
    return context


class WalletPush:
    def __init__(self, client: httpx.Client | None):
        self.client = client
        self.lock = threading.Lock()

    @classmethod
    def from_signer(cls, folder: Path, signer: Signer | None) -> "WalletPush":
        if not signer:
            return cls(None)
        try:
            return cls(httpx.Client(http2=True, verify=tls_context(folder, signer), timeout=10))
        except (ssl.SSLError, OSError) as e:
            log.error("Wallet : push impossible, certificat TLS refusé (%s)", type(e).__name__)
            return cls(None)

    def send(self, tokens: list[str]) -> int:
        """Un push vide par jeton ; rend le nombre de push acceptés par Apple."""
        if not self.client:
            return 0
        sent = 0
        for token in list(dict.fromkeys(tokens))[:MAX_TOKENS]:
            try:
                with self.lock:  # une connexion HTTP/2 partagée
                    r = self.client.post(f"{GATEWAY}/3/device/{token}", content=b"{}",
                                         headers={"apns-topic": PASS_TYPE_ID, "apns-push-type": "background",
                                                  "apns-priority": "5"})
            except httpx.HTTPError as e:
                log.warning("Wallet : APNs injoignable (%s)", type(e).__name__)
                return sent
            if r.status_code == 200:
                sent += 1
            elif r.status_code not in GONE:
                log.warning("Wallet : APNs a refusé un push (%s %s)", r.status_code, r.text[:200])
        return sent
