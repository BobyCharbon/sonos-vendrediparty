"""« Ajouter à Apple Wallet » sous le billet d'un événement, et mises à jour automatiques du pass.

Ajout : même vérification que pour afficher son billet (jeton Supabase du membre ; la base décide via
wallet_pass_issue → my_event_ticket : Présent, hors liste d'attente, événement publié qu'il voit, « Billets QR »
activés et billet remis par l'organisateur, migration 20261104233000). Jamais le billet
d'un autre. Safari ouvre un .pkpass par une simple navigation (pas de jeton dans l'adresse) : le billet est préparé
à la demande (POST avec le jeton), gardé quelques minutes sous un lien aléatoire, puis téléchargé par ce lien.

Mises à jour (PassKit Web Service, sans session) : l'iPhone ne présente que le jeton propre au pass
(authenticationToken) ou l'identifiant de son appareil ; la base ne rend que ce pass-là (migration
20261103160000_wallet_passes). Après un changement, l'écran qui l'a fait demande les push (notify) : la base dit
quels appareils prévenir, selon les droits de la personne connectée."""
import logging
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx

from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError, Accounts
from .wallet import Signer, WalletError, images, package, ticket_pass
from .wallet_push import WalletPush

log = logging.getLogger(__name__)

LINK_TTL = 300
MAX_LINKS = 500
MISSING_FUNCTION = "PGRST202"


class WalletTickets:
    def __init__(self, accounts: Accounts, folder: Path, push: WalletPush | None = None):
        self.accounts = accounts
        self.folder = folder
        self.signer = Signer.from_dir(folder)
        self.images = images() if self.signer else {}
        self.push = push if push is not None else WalletPush.from_signer(folder, self.signer)
        self.lock = threading.Lock()
        self.links: dict[str, tuple[float, bytes]] = {}

    @property
    def enabled(self) -> bool:
        return self.signer is not None

    # --- appels à la base -------------------------------------------------------------------------------------

    def _member_rpc(self, name: str, token: str, args: dict):
        r = self.accounts._get("POST", f"/rest/v1/rpc/{name}", token, json=args)
        if r.status_code == 401 or (r.status_code == 403 and "JWT" in r.text):
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        if r.status_code >= 400:
            message = _message(r)
            raise WalletError(message if r.status_code == 400 and message else "Ton billet n'a pas pu être lu. Réessaie.")
        return r.json()

    def _anon_rpc(self, name: str, args: dict):
        """Appel sans session (iPhone → PassKit Web Service) : la fonction vérifie le jeton du pass."""
        try:
            r = self.accounts.client.post(f"{SUPABASE_URL}/rest/v1/rpc/{name}", json=args,
                                          headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"})
        except httpx.HTTPError as e:
            raise WalletError("Base injoignable") from e
        if r.status_code >= 400:
            raise WalletError(_message(r) or "Refusé")
        return r.json() if r.content.strip() else None

    # --- pass -------------------------------------------------------------------------------------------------

    def _package(self, payload: dict, origin: str) -> bytes:
        if not self.signer:
            raise WalletError("Wallet pas encore configuré.")
        data = ticket_pass(origin=origin, event=payload["event"], ticket=payload.get("ticket") or {},
                           holder=(payload.get("holder") or "Participant").strip(), user_id=str(payload["user_id"]),
                           auth_token=payload.get("auth_token"), valid=bool(payload.get("valid")))
        return package(data, self.images, self.signer)

    def build(self, token: str, event_id: str, origin: str) -> bytes:
        """Le .pkpass du billet de la personne connectée (WalletError s'il n'y a pas de billet)."""
        if not self.signer:
            raise WalletError("Wallet pas encore configuré.")
        self.accounts._uid(token)  # session valable, sinon « Reconnecte-toi »
        payload = self._member_rpc("wallet_pass_issue", token, {"e": event_id})
        if not isinstance(payload, dict) or not payload.get("valid"):
            raise WalletError("Pas encore de billet pour cet événement : l'organisateur doit te le remettre.")
        return self._package(payload, origin)

    def prepare(self, token: str, event_id: str, origin: str) -> str:
        """Prépare le billet ; rend l'identifiant du lien de téléchargement (valable LINK_TTL secondes)."""
        data = self.build(token, event_id, origin)
        link = secrets.token_urlsafe(24)
        now = time.time()
        with self.lock:
            self.links = {k: v for k, v in self.links.items() if now - v[0] < LINK_TTL}
            if len(self.links) >= MAX_LINKS:
                self.links.pop(next(iter(self.links)))
            self.links[link] = (now, data)
        return link

    def download(self, link: str) -> bytes | None:
        with self.lock:
            hit = self.links.get(link)
        if not hit or time.time() - hit[0] >= LINK_TTL:
            return None
        return hit[1]

    # --- PassKit Web Service ----------------------------------------------------------------------------------

    def latest(self, auth_token: str, serial: str, origin: str) -> tuple[bytes, datetime] | None:
        """Le pass à jour et sa date de modification ; None si le jeton ne correspond pas à ce pass."""
        payload = self._anon_rpc("wallet_pass_by_token", {"tok": auth_token, "serial": serial})
        if not isinstance(payload, dict) or not payload.get("event"):
            return None
        return self._package(payload, origin), _moment(payload["updated_at"])

    def register(self, auth_token: str, serial: str, device: str, push_token: str) -> str:
        return str(self._anon_rpc("wallet_register", {"tok": auth_token, "serial": serial, "device": device, "push": push_token}))

    def unregister(self, auth_token: str, serial: str, device: str) -> bool:
        return bool(self._anon_rpc("wallet_unregister", {"tok": auth_token, "serial": serial, "device": device}))

    def updated(self, device: str, since: str | None) -> dict:
        return self._anon_rpc("wallet_updated_serials", {"device": device, "since": since})

    def push_targets(self, token: str, event_id: str, member: str | None) -> list[str]:
        """Jetons de push des pass à prévenir (droits vérifiés par la base). Base sans la migration : aucun."""
        r = self.accounts._get("POST", "/rest/v1/rpc/wallet_push_targets", token, json={"e": event_id, "member": member})
        if r.status_code == 404 and MISSING_FUNCTION in r.text:
            return []
        if r.status_code == 401:
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        if r.status_code >= 400:
            raise WalletError(_message(r) or "Refusé")
        return [t for t in r.json() if isinstance(t, str)]

    def notify(self, tokens: list[str]) -> int:
        return self.push.send(tokens) if tokens else 0


def _message(r: httpx.Response) -> str:
    try:
        return str(r.json().get("message") or "")
    except (ValueError, AttributeError):
        return ""


def _moment(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
