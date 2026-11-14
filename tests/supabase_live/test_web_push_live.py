"""Web Push sur la VRAIE base de test et le VRAI envoi (cron → fonction send-web-push → service push de Google) :
- un appareil du web s'inscrit (register_web_push), demande une notification d'essai (test_web_push) ;
- l'envoi part vers Google, qui répond que cet abonnement n'existe pas (adresse inventée, comme un navigateur
  désinstallé) : la base l'oublie (finish_web_push_delivery 404/410), l'appareil n'est plus « activé ».
Seuls des comptes de test (numéros 4179000…) et des adresses inventées : personne n'est prévenu.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_web_push_live.py -q"""
import base64
import secrets
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from tests.supabase_live.test_audiences_live import GUEST_A, VIP
from tests.supabase_live.test_member_admin_live import Session, pytestmark  # noqa: F401

ORIGIN = 'https://partytest.bobycharbon.ch'


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def fake_device() -> dict:
    point = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {'endpoint': f'https://fcm.googleapis.com/fcm/send/vp-test-{secrets.token_hex(12)}',
            'keys': {'p256dh': b64(point), 'auth': b64(secrets.token_bytes(16))}}


def register(s: Session) -> str:
    device = fake_device()
    r = s.rpc('register_web_push', device_subscription=device, device_origin=ORIGIN)
    assert r.status_code in (200, 204), r.text
    assert s.rpc('web_push_device_status', device_endpoint=device['endpoint']).json() is True
    return device['endpoint']


def try_test(s: Session, endpoint: str):
    for _ in range(3):  # une notification d'essai par minute et par compte
        r = s.rpc('test_web_push', device_endpoint=endpoint)
        if r.status_code in (200, 204):
            return
        assert 'minute' in r.text, r.text
        time.sleep(61)
    raise AssertionError(r.text)


def gone_within(s: Session, endpoint: str, seconds: int) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if s.rpc('web_push_device_status', device_endpoint=endpoint).json() is False:
            return True
        time.sleep(10)
    return False


@pytest.fixture(scope='module')
def member():
    return Session(VIP)


@pytest.fixture(scope='module')
def guest():
    return Session(GUEST_A)


def test_an_expired_web_subscription_is_forgotten_after_a_real_send(member):
    endpoint = register(member)
    try:
        try_test(member, endpoint)
        assert gone_within(member, endpoint, 240), "abonnement refusé par Google mais gardé par la base"
    finally:
        member.rpc('unregister_web_push', device_endpoint=endpoint)


def test_a_guest_test_notification_is_really_sent(guest):
    """Le bandeau « Ne rate rien de cet événement » et « Envoyer une notification d'essai » sont offerts à tout le monde,
    Guest compris : son navigateur s'inscrit et l'essai part (migration 20261114200000_web_push_guests ; avant elle,
    register_web_push répond « Connexion requise » à un Guest)."""
    endpoint = register(guest)
    try:
        try_test(guest, endpoint)
        assert gone_within(guest, endpoint, 240), "l'essai d'un Guest n'est jamais envoyé (private.may_receive_push)"
    finally:
        guest.rpc('unregister_web_push', device_endpoint=endpoint)
