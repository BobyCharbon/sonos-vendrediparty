"""Compagnon — certificats d'authenticité des Légendaires et Mythiques (lot A, 4.11.2026). PAS de NFT, pas de chaîne.

Chaque exemplaire frappé en base (public.pet_items : objet, numéro, tirage, date, origine) reçoit un certificat SIGNÉ
par le serveur Party avec une clé Ed25519. La clé privée est dérivée de la clé du serveur (PET_SECRET, jamais envoyée
au navigateur ni écrite dans le dépôt) ; la clé PUBLIQUE est publiée (GET /api/pet/certificats/cle) : n'importe qui
peut vérifier qu'un certificat vient bien de Party et n'a pas été retouché. Le code court (ZC-7F3A-K9Q2-M4XD) est tiré
de la signature : il sert à retrouver le certificat (« Vérifier un objet »).
La provenance (historique des propriétaires) est gardée en base (public.pet_item_owners) et montrée avec le certificat.
"""
import base64
import hashlib
import hmac

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

FORMAT = "ZC1"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sans 0/O ni 1/I : lisible à voix haute
CODE_GROUPS = 3


def private_key(secret: str | bytes) -> Ed25519PrivateKey:
    root = secret.encode() if isinstance(secret, str) else secret
    seed = hmac.new(root, b"party-pet:cert:ed25519:v1", hashlib.sha256).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_b64(secret: str | bytes) -> str:
    raw = private_key(secret).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def fingerprint(public_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(public_b64)).hexdigest()[:16]


def payload(inst: dict) -> str:
    """Texte signé (ordre et format fixes) : exemplaire, objet, numéro / tirage, date de frappe, origine."""
    edition = inst.get("edition") or 0
    return "|".join([FORMAT, str(inst["id"]), str(inst["item"]), str(int(inst["serial"])), str(int(edition)),
                     str(inst["minted_at"]), str(inst.get("source") or "")])


def code_of(signature_b64: str) -> str:
    digest = hashlib.sha256(base64.b64decode(signature_b64)).digest()
    n = int.from_bytes(digest[:8], "big")
    chars = []
    for _ in range(4 * CODE_GROUPS):
        chars.append(ALPHABET[n % len(ALPHABET)])
        n //= len(ALPHABET)
    text = "".join(chars)
    return "ZC-" + "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def sign(secret: str | bytes, inst: dict) -> dict:
    """{payload, sig (base64), code} pour un exemplaire frappé."""
    text = payload(inst)
    sig = base64.b64encode(private_key(secret).sign(text.encode())).decode()
    return {"payload": text, "sig": sig, "code": code_of(sig)}


def verify(public_b64: str, text: str, sig_b64: str) -> bool:
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        key.verify(base64.b64decode(sig_b64), text.encode())
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def normalize_code(code: str) -> str:
    """« zc 7f3a k9q2 m4xd » → « ZC-7F3A-K9Q2-M4XD » (ou chaîne vide si ce n'est pas un code)."""
    raw = "".join(c for c in str(code or "").upper() if c.isalnum())
    if raw.startswith("ZC"):
        raw = raw[2:]
    if len(raw) != 4 * CODE_GROUPS or any(c not in ALPHABET for c in raw):
        return ""
    return "ZC-" + "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))
