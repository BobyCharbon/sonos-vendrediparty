"""Réglage du volume fluide (soirée du 05.11.2026) : une enceinte qui décroche du Wi-Fi (« SONOS Salle de Bain ») ne doit
bloquer ni le volume des autres, ni la liste des enceintes, ni les requêtes pendant le rafraîchissement des zones.
SoCo attend 20 s par défaut : les réglages de volume passent un délai court, le reste un délai réduit."""
import threading
import time
from unittest import mock

from app import sonos


class Zone:
    def __init__(self, uid, name, volume=30, dead=False):
        self.uid, self.ip_address, self.is_visible, self.player_name = uid, "192.168.50.1", True, name
        self.dead = dead
        self.renderingControl = mock.Mock()
        self.groupRenderingControl = mock.Mock()
        if dead:
            self.renderingControl.GetVolume.side_effect = TimeoutError("timed out")
        else:
            self.renderingControl.GetVolume.return_value = {"CurrentVolume": str(volume)}
        self.group = mock.Mock(coordinator=self, members=[self])


def _with_zones(*zones):
    s = sonos.Sonos(seed_ip="192.168.50.186")
    s._zones = {z.uid: z for z in zones}
    s._zones_at = time.time()
    return s


def test_soco_default_timeout_is_short():
    assert sonos.soco.config.REQUEST_TIMEOUT <= 5


def test_speaker_volume_uses_a_short_timeout():
    salon = Zone("RINCON_SALON", "Salon")
    s = _with_zones(salon)
    s.set_speaker_volume("RINCON_SALON", 42)
    args, kwargs = salon.renderingControl.SetVolume.call_args
    assert ("DesiredVolume", 42) in args[0]
    assert kwargs["timeout"] <= sonos.VOLUME_TIMEOUT <= 3


def test_group_volume_uses_a_short_timeout():
    salon = Zone("RINCON_SALON", "Salon")
    salon.group.members = [salon, Zone("RINCON_B", "Bain")]
    s = _with_zones(salon)
    s.set_volume("RINCON_SALON", 55)
    args, kwargs = salon.groupRenderingControl.SetGroupVolume.call_args
    assert ("DesiredVolume", 55) in args[0]
    assert kwargs["timeout"] <= 3


def test_group_volume_801_takes_a_snapshot_then_retries():
    salon = Zone("RINCON_SALON", "Salon")
    salon.group.members = [salon, Zone("RINCON_B", "Bain")]
    salon.groupRenderingControl.SetGroupVolume.side_effect = [sonos.SoCoUPnPException("801", 801, ""), None]
    s = _with_zones(salon)
    s.set_volume("RINCON_SALON", 20)
    assert salon.groupRenderingControl.SnapshotGroupVolume.called
    assert salon.groupRenderingControl.SetGroupVolume.call_count == 2


def test_a_speaker_that_does_not_answer_is_left_out_of_the_list():
    salon, bain = Zone("RINCON_SALON", "Salon", 12), Zone("RINCON_BAIN", "SONOS Salle de Bain", dead=True)
    s = _with_zones(salon, bain)
    speakers = s.speakers("RINCON_SALON")
    assert [sp["name"] for sp in speakers] == ["Salon"]
    assert speakers[0]["volume"] == 12
    _, kwargs = bain.renderingControl.GetVolume.call_args
    assert kwargs["timeout"] <= 3


def test_stale_zones_are_refreshed_in_the_background_without_blocking_requests():
    salon = Zone("RINCON_SALON", "Salon")
    s = _with_zones(salon)
    s._zones_at = 0  # périmé : le rafraîchissement doit partir en arrière-plan
    release = threading.Event()

    class SlowSeed:
        @property
        def all_zones(self):
            release.wait(5)
            return {salon}

    with mock.patch.object(sonos.soco, "SoCo", return_value=SlowSeed()):
        started = time.monotonic()
        s.set_speaker_volume("RINCON_SALON", 30)
        s.set_speaker_volume("RINCON_SALON", 31)
        elapsed = time.monotonic() - started
        release.set()
        s._refresher.join(5)
    assert elapsed < 0.5
    assert s._zones_at > 0


def test_first_listing_still_waits_for_the_zones():
    salon = Zone("RINCON_SALON", "Salon")
    s = sonos.Sonos(seed_ip="192.168.50.186")
    with mock.patch.object(sonos.soco, "SoCo", return_value=mock.Mock(all_zones={salon})):
        assert s.coordinator("RINCON_SALON") is salon
