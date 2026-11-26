"""Suppression du compte (Apple 5.1.1(v), nLPD art. 5 let. c et 6) : tout ce que le serveur Party garde sur le compte
dans ses fichiers locaux part avec lui, quel que soit le chemin (app iOS : /api/account/delete ; module web :
/api/account/delete aussi). La base Supabase, elle, efface ses lignes par delete_my_account (cascade).

Effacé ici : stats du Purify Test et du Quiz, journal des appels à l'IA (avec ce qui a été dicté), accords IA (avis et
assistant), compteur de parties en invité, état de son Zicou et ses bandeaux (pet_party.json). Ses avis restent (retours
sur l'app) mais anonymisés. Journal d'administration (audit.jsonl, 12 mois) : ses connexions partent, les actions d'admin
qui le visaient restent (sécurité) sans son nom."""
import logging
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalStores:
    """Les fichiers locaux liés à un compte, et comment effacer chacun (une fonction par fichier)."""
    purity_forget: Callable[[str], bool]
    quiz_forget: Callable[[str], bool]
    usage_forget: Callable[[set[str]], int]
    consent_forget: Callable[[str], None]
    gate_forget: Callable[[str], None]
    feedback_forget: Callable[[str], int]
    activity_forget: Callable[[str], None]
    audit_forget: Callable[[str], int] = lambda gid: 0


def subjects(uid: str) -> set[str]:
    """Identifiants sous lesquels un compte apparaît dans le journal de l'IA et les accords."""
    return {uid, "acct:" + uid}


def forget_local(stores: LocalStores, uid: str, gid: str, consent_keys: tuple[str, ...]) -> dict:
    """Efface tout ce qui est lié au compte `uid` (identifiant de joueur `gid`, signé par le serveur : accounts.gid) ;
    chaque fichier est tenté même si un autre échoue (disque, format). Renvoie ce qui a été fait (pour les tests et le
    journal du serveur, jamais montré à la personne)."""
    steps = {
        "purity": lambda: stores.purity_forget(gid),
        "quiz": lambda: stores.quiz_forget(gid),
        "ai_usage": lambda: stores.usage_forget(subjects(uid)),
        "consents": lambda: [stores.consent_forget(key) for key in consent_keys],
        "guest_gate": lambda: stores.gate_forget(gid),
        "feedback": lambda: stores.feedback_forget(gid),
        "pet_party": lambda: stores.activity_forget(gid),
        "audit": lambda: stores.audit_forget(gid),
    }
    done: dict = {}
    for name, step in steps.items():
        try:
            done[name] = step()
        except Exception as e:  # un fichier abîmé n'empêche pas d'effacer les autres ; l'erreur va au journal
            log.warning("Suppression du compte : %s non effacé (%s: %s)", name, type(e).__name__, e)
            done[name] = "error"
    return done


def activity_forgetter(activity_log) -> Callable[[str], None]:
    """Journal d'activité de Zicou (pet_party.json, app/pet_reactions.ActivityLog) : notes, état du Zicou, proposition
    d'adoption, choix « réactions coupées » et bandeaux en attente du compte."""
    def forget(gid: str) -> None:
        with activity_log.lock:
            activity_log.rows.pop(gid, None)
            activity_log.pets.pop(gid, None)
            activity_log.offered.pop(gid, None)
            activity_log.quiet.discard(gid)
            activity_log.pending.pop(gid, None)
            activity_log._write()
    return forget
