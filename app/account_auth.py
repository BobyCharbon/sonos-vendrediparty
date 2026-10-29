"""Connexion native (app iOS) : code SMS, session, déconnexion et suppression du compte, sans passer par la page.
La session obtenue est la même que celle du module Événements (supabase-js) : l'app la range là où la page la lit
(storage_key dans le localStorage du site), si bien que la page, les jeux et les Réglages natifs partagent le compte."""
import re
import time
from urllib.parse import urlparse

from . import accounts as accounts_mod
from .accounts import AccountError, Accounts

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
CONFIRM_DELETE = "SUPPRIMER"


def storage_key() -> str:
    """Clé de la session dans le localStorage du site, comme supabase-js : sb-<projet>-auth-token."""
    host = urlparse(accounts_mod.SUPABASE_URL).hostname or ""
    return f"sb-{host.split('.')[0]}-auth-token"


def _message(r, fallback: str) -> str:
    try:
        data = r.json()
    except ValueError:
        return fallback
    text = str(data.get("msg") or data.get("message") or data.get("error_description") or "")
    return text or fallback


class AccountAuth:
    def __init__(self, accounts: Accounts):
        self.accounts = accounts

    def _auth(self, method: str, path: str, **kw):
        # Avant connexion, la clé publique sert aussi de jeton (comme supabase-js).
        return self.accounts._get(method, path, accounts_mod.SUPABASE_ANON_KEY, **kw)

    def send_code(self, phone: str) -> None:
        if not E164.match(phone):
            raise AccountError("Numéro invalide : vérifie le pays et le numéro.")
        r = self._auth("POST", "/auth/v1/otp", json={"phone": phone})
        if r.status_code == 429:
            raise AccountError("Trop de codes demandés : attends une minute puis réessaie.")
        if r.status_code not in (200, 204):
            raise AccountError(_message(r, "Le code n'a pas pu être envoyé. Réessaie dans un instant."))

    def verify(self, phone: str, code: str) -> dict:
        """Code reçu → session (jetons + compte) et la clé où la page la range."""
        if not E164.match(phone) or not re.fullmatch(r"\d{6}", code):
            raise AccountError("Code incorrect ou expiré")
        r = self._auth("POST", "/auth/v1/verify", json={"type": "sms", "phone": phone, "token": code})
        session = r.json() if r.status_code == 200 else None
        if not isinstance(session, dict) or not session.get("access_token"):
            raise AccountError("Code incorrect ou expiré")
        if not session.get("expires_at"):
            session["expires_at"] = int(time.time()) + int(session.get("expires_in") or 3600)
        return {"session": session, "storage_key": storage_key()}

    def sign_out(self, token: str) -> None:
        """Ferme la session de cet appareil (les autres appareils restent connectés). Déjà expirée : rien à faire."""
        try:
            self.accounts._get("POST", "/auth/v1/logout?scope=local", token)
        except AccountError:
            pass  # hors ligne : l'app oublie quand même la session ; elle expirera d'elle-même

    def delete_account(self, token: str, confirm: str) -> None:
        if confirm.strip() != CONFIRM_DELETE:
            raise AccountError(f"Écris {CONFIRM_DELETE} pour confirmer.")
        self.accounts._uid(token)
        r = self.accounts._get("POST", "/rest/v1/rpc/delete_my_account", token, json={})
        if r.status_code not in (200, 204):
            if "last_admin" in r.text:
                raise AccountError("Tu es le dernier administrateur : désigne d'abord un autre administrateur actif dans Membres.")
            raise AccountError("Ton compte n'a pas pu être supprimé. Vérifie ta connexion et réessaie.")
        self.sign_out(token)
