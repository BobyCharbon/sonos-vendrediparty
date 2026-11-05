"""Noms des contacts (app iPhone) : relais entre l'app et la base, avec la session de la personne.

L'iPhone demande la clé des empreintes (contacts_key), calcule HMAC-SHA256(clé, numéro E.164) pour chaque numéro de
son répertoire et n'envoie QUE ces empreintes (contacts_match). La base renvoie les comptes actifs correspondants
({user_id, hash}) ; elle applique la limite de débit et ne garde aucune empreinte. Ce serveur ne garde rien non plus.
"""
import re

from .accounts import PHOTO_TTL, SUPABASE_URL, AccountError, Accounts

MAX_HASHES = 20000
MAX_FRIENDS = 2000  # contacts_friends : comptes reconnus demandés en une fois
HASH = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def signed_photos(accounts: Accounts, token: str, paths: list) -> dict[str, str]:
    """Liens signés des photos de profil (bucket privé), en une seule requête, avec la session de la personne."""
    wanted = sorted({p for p in paths if isinstance(p, str) and p})
    if not wanted:
        return {}
    r = accounts._get("POST", "/storage/v1/object/sign/profile-photos", token, json={"expiresIn": PHOTO_TTL, "paths": wanted})
    rows = r.json() if r.status_code == 200 else []
    return {row["path"]: SUPABASE_URL + "/storage/v1" + row["signedURL"]
            for row in rows if isinstance(row, dict) and row.get("signedURL") and row.get("path")}


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

    def friends(self, token: str, ids: list[str]) -> list[dict]:
        """Mes amis dans Party : pour les comptes déjà reconnus sur l'iPhone, surnom, photo (lien signé), arrivée et groupes en commun.
        Jamais de numéro ni de rôle : seuls ces champs sont relayés, et seulement pour les comptes demandés."""
        unique = sorted({i.lower() for i in ids})
        if len(unique) > MAX_FRIENDS:
            raise AccountError("Trop de contacts d'un coup.")
        if any(not UUID.match(i) for i in unique):
            raise AccountError("Identifiant invalide.")
        if not unique:
            return []
        rows = self.accounts._rpc_json(token, "contacts_friends", {"ids": unique},
                                       "Tes amis n'ont pas pu être chargés. Réessaie plus tard.")
        asked = set(unique)
        rows = [r for r in rows or [] if isinstance(r, dict) and r.get("id") in asked]
        photos = signed_photos(self.accounts, token, [r.get("avatar_url") for r in rows])
        return [{"id": r["id"], "display_name": str(r.get("display_name") or ""), "photo": photos.get(r.get("avatar_url")),
                 "joined_at": r.get("joined_at"),
                 "common_groups": [str(g) for g in r.get("common_groups") or [] if isinstance(g, str)]}
                for r in rows]
