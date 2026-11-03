"""Noms des contacts (app iPhone) : relais entre l'app et la base, avec la session de la personne.

L'iPhone demande la clé des empreintes (contacts_key), calcule HMAC-SHA256(clé, numéro E.164) pour chaque numéro de
son répertoire et n'envoie QUE ces empreintes (contacts_match). La base renvoie les comptes actifs correspondants
({user_id, hash}) ; elle applique la limite de débit et ne garde aucune empreinte. Ce serveur ne garde rien non plus.
"""
import re

from .accounts import AccountError, Accounts

MAX_HASHES = 20000
HASH = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ContactNames:
    def __init__(self, accounts: Accounts):
        self.accounts = accounts

    def key(self, token: str) -> str:
        key = self.accounts._rpc_json(token, "contacts_key", {}, "La reconnaissance des contacts est indisponible.")
        if not isinstance(key, str) or not HASH.match(key):
            raise AccountError("La reconnaissance des contacts est indisponible.")
        return key

    def match(self, token: str, hashes: list[str]) -> list[dict]:
        unique = sorted({h.lower() for h in hashes})
        if len(unique) > MAX_HASHES:
            raise AccountError("Trop de numéros d'un coup.")
        if any(not HASH.match(h) for h in unique):
            raise AccountError("Empreinte invalide.")
        rows = self.accounts._rpc_json(token, "contacts_match", {"hashes": unique},
                                       "Tes contacts n'ont pas pu être comparés. Réessaie plus tard.")
        sent = set(unique)
        # Seulement ce qui a été demandé, sous une forme fixe (jamais d'autre champ venu de la base).
        return [{"user_id": r["user_id"], "hash": r["hash"]} for r in rows or []
                if isinstance(r, dict) and UUID.match(str(r.get("user_id", ""))) and r.get("hash") in sent]
