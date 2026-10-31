"""Sonos en lecture aléatoire : il refuse un titre inséré à une position précise (erreur UPnP 800). L'app ajoute
alors le titre « à jouer ensuite », ce que Sonos accepte en aléatoire."""
from app import sonos


class FakeCoordinator:
    def __init__(self, play_mode):
        self.play_mode = play_mode


def adds(monkeypatch, play_mode):
    calls = []

    class FakeShare:
        def __init__(self, coord):
            pass

        def add_share_link_to_queue(self, uri, position=0, as_next=False, **kwargs):
            calls.append({"uri": uri, "position": position, "as_next": as_next, **kwargs})
            return 7

    monkeypatch.setattr(sonos, "ShareLinkPlugin", FakeShare)
    player = sonos.Sonos.__new__(sonos.Sonos)
    monkeypatch.setattr(player, "coordinator", lambda uid: FakeCoordinator(play_mode), raising=False)
    player.add_spotify_track("RINCON_X", "4Jhg28dTdA04Cu0UK33RY3", "Mami Wata", 499)
    return calls


def test_in_order_the_track_goes_to_its_position(monkeypatch):
    [call] = adds(monkeypatch, "NORMAL")
    assert call["position"] == 499 and not call["as_next"]


def test_in_shuffle_the_track_is_played_next_instead_of_a_position(monkeypatch):
    for mode in ("SHUFFLE", "SHUFFLE_NOREPEAT", "SHUFFLE_REPEAT_ONE"):
        [call] = adds(monkeypatch, mode)
        assert call["position"] == 0 and call["as_next"], mode


def test_the_title_is_escaped_for_the_sonos_xml(monkeypatch):
    # « HAINE&SEX » : un & brut rend les métadonnées XML invalides et Sonos refuse l'ajout (erreur UPnP 800).
    calls = []

    class FakeShare:
        def __init__(self, coord):
            pass

        def add_share_link_to_queue(self, uri, position=0, as_next=False, **kwargs):
            calls.append(kwargs["dc_title"])
            return 1

    monkeypatch.setattr(sonos, "ShareLinkPlugin", FakeShare)
    player = sonos.Sonos.__new__(sonos.Sonos)
    for mode in ("NORMAL", "SHUFFLE"):
        monkeypatch.setattr(player, "coordinator", lambda uid, m=mode: FakeCoordinator(m), raising=False)
        player.add_spotify_track("RINCON_X", "2Ye307CcSIpAOjBF3aD46f", "HAINE&SEX <live>", 3)
    assert calls == ["HAINE&amp;SEX &lt;live&gt;"] * 2
