"""Une enceinte Sonos éteinte (encore annoncée dans le groupe) ne doit pas empêcher de lister ni d'utiliser les autres
(bug du 05.11.2026 : « No route to host » sur 192.168.50.182 bloquait le démarrage de la soirée)."""
from unittest import mock

from app import sonos


class Dead:
    uid, ip_address, is_visible = "RINCON_DEAD", "192.168.50.182", True

    @property
    def player_name(self):
        raise ConnectionError("No route to host")

    @property
    def group(self):
        raise ConnectionError("No route to host")


class Alive:
    def __init__(self, uid, name):
        self.uid, self.ip_address, self.is_visible, self.player_name = uid, "192.168.50.186", True, name
        self.group = mock.Mock(coordinator=self, members=[self, Dead()])


def test_a_dead_speaker_is_skipped_and_the_others_are_listed():
    living = Alive("RINCON_SALON", "Salon")
    s = sonos.Sonos(seed_ip="192.168.50.186")
    with mock.patch.object(sonos.soco, "SoCo", return_value=mock.Mock(all_zones={living, Dead()})):
        rooms = s.rooms()
    assert rooms == [{"uid": "RINCON_SALON", "name": "Salon", "spotify_name": "Salon"}]
    assert s.coordinator("RINCON_SALON") is living
