"""Fonctions en bêta : allumées sur le site de test, éteintes en production, sans dépendre d'une branche.

Compagnon (Zicou) : reste en bêta tant que l'admin n'a pas dit « le projet Compagnon est complet ».
develop est mergé dans main pour d'autres sujets : c'est l'adresse du site (ou COMPAGNON_ENABLED) qui décide.
"""
import os
from urllib.parse import urlparse

TEST_SITE_HOST = "partytest.bobycharbon.ch"
COMPAGNON_SOON = "Zicou arrive bientôt."
PATATES_SOON = "Bientôt"


def configured_public_url() -> str:
    # Une adresse propre à chaque déploiement pour les QR et le retour OAuth Spotify.
    # Ne pas reprendre l'ancienne variable PUBLIC_URL, encore locale sur certaines stacks.
    return (os.environ.get("PARTY_PUBLIC_URL") or "https://party.bobycharbon.ch").rstrip("/")


def app_store_url() -> str:
    """Fiche de l'app VendrediParty sur l'App Store (même adresse que web/events/src/lib/appInvite.ts)."""
    return (os.environ.get("PARTY_APP_STORE_URL") or "https://apps.apple.com/app/id6827221948").strip()


def is_test_site() -> bool:
    return urlparse(configured_public_url()).hostname == TEST_SITE_HOST


def _flag(name: str) -> bool:
    """Variable "1" / "0" si elle est définie ; sinon allumé sur le site de test seulement."""
    flag = os.environ.get(name, "").strip()
    if flag in ("0", "1"):
        return flag == "1"
    return is_test_site()


def compagnon_enabled(request=None) -> bool:
    """COMPAGNON_ENABLED ("1" / "0") si elle est définie ; sinon allumé sur le site de test seulement.
    request de l'app App Store (store_app.is_store) : toujours éteint (contrôle Apple du 26.11)."""
    if request is not None:
        from . import store_app  # store_app importe ce module
        if store_app.is_store(request):
            return False
    return _flag("COMPAGNON_ENABLED")


def discussions_enabled() -> bool:
    """Discussions (groupes et messages directs) : DISCUSSIONS_ENABLED ("1" / "0") si elle est définie ; sinon
    allumées sur le site de test seulement (décision du 04.11 : absentes de la production, ni onglet ni « Bientôt »)."""
    return _flag("DISCUSSIONS_ENABLED")


def invites_v2_enabled() -> bool:
    """Invitations v2 (carte « Invités », liens pour plusieurs, réponse sans app) : INVITES_V2_ENABLED ("1" / "0") si elle
    est définie ; sinon allumées sur le site de test seulement (bêta, décision du 05.11 : la prod quand l'admin le dira)."""
    return _flag("INVITES_V2_ENABLED")


def bar_enabled() -> bool:
    """Bar de la soirée (articles, stock, commandes, QR, barmans ; maquettes v6 du 10.11) : BAR_ENABLED ("1" / "0") si elle
    est définie ; sinon allumé sur le site de test seulement (en construction : la prod après recette et « Ok prod »)."""
    return _flag("BAR_ENABLED")


def patates_enabled() -> bool:
    """Patates des Pronos v2 (monnaie fictive, gratuite, sans valeur ; 18.11) : PATATES_ENABLED ("1" / "0") si elle est
    définie ; sinon allumées sur le site de test seulement. Éteintes : les pronos restent pour l'honneur (points)."""
    return _flag("PATATES_ENABLED")


def agenda_enabled() -> bool:
    """Agenda (rendez-vous, dispos partagées, liens de dispo publics ; 17.11) : AGENDA_ENABLED ("1" / "0") si elle est
    définie ; sinon allumé sur le site de test seulement (décision du 19.11 : gardé en test, l'admin l'améliore)."""
    return _flag("AGENDA_ENABLED")


def pronos_enabled() -> bool:
    """Pronos entre amis (17-18.11) : PRONOS_ENABLED ("1" / "0") si elle est définie ; sinon allumés sur le site de test
    seulement (décision du 19.11 : gardés en test). Éteints, les confettis le sont aussi (patates_enabled)."""
    return _flag("PRONOS_ENABLED")


def _off_in_store(request) -> bool:
    if request is None:
        return False
    from . import store_app  # store_app importe ce module
    return store_app.is_store(request)


def souvenirs_enabled(request=None) -> bool:
    """Souvenirs (photos de la soirée ; 24.11) : SOUVENIRS_ENABLED ("1" / "0") si elle est définie ; sinon allumés sur le
    site de test seulement. request de l'app App Store : toujours éteints (contrôle Apple du 26.11)."""
    return not _off_in_store(request) and _flag("SOUVENIRS_ENABLED")


def covers_enabled(request=None) -> bool:
    """Couverture d'événement changée après coup (25.11) : COVERS_ENABLED ("1" / "0") si elle est définie ; sinon allumée
    sur le site de test seulement. request de l'app App Store : toujours éteinte (contrôle Apple du 26.11)."""
    return not _off_in_store(request) and _flag("COVERS_ENABLED")
