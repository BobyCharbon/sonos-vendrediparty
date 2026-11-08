"""Retour de l'admin (08.11) : trois enceintes groupées pour la soirée ; on retire du groupe (app Sonos) l'enceinte de la
soirée. Sonos continue la musique sur les deux autres, mais Party regardait l'enceinte retirée (arrêtée) et affichait
« en pause » : il fallait recréer la soirée. Party suit maintenant le groupe qui continue."""
from app import sonos


class Group:
    def __init__(self, coordinator, members):
        self.coordinator, self.members = coordinator, members


class Zone:
    def __init__(self, uid, playing=False):
        self.uid, self.group, self.playing = uid, None, playing

    def get_current_transport_info(self):
        return {"current_transport_state": "PLAYING" if self.playing else "STOPPED"}


def regroup(coordinator, *members):
    g = Group(coordinator, [coordinator, *members])
    for z in g.members:
        z.group = g


def player(*zones):
    s = sonos.Sonos(seed_ip="127.0.0.1")
    s._zones = {z.uid: z for z in zones}
    s._zones_at = 10 ** 12  # jamais périmées pendant le test
    return s


def test_the_party_follows_the_group_when_its_speaker_is_removed_from_it():
    salon, cuisine, bain = Zone("salon"), Zone("cuisine"), Zone("bain")
    regroup(salon, cuisine, bain)
    s = player(salon, cuisine, bain)
    assert s.coordinator("salon") is salon
    # Le salon (enceinte de la soirée) sort du groupe : Sonos confie la musique à la cuisine.
    regroup(cuisine, bain)
    regroup(salon)
    assert s.coordinator("salon") is cuisine
    assert s.coordinator("salon") is cuisine  # et ça tient aux lectures suivantes
    # Le salon revient dans le groupe : tout redevient normal.
    regroup(cuisine, bain, salon)
    assert s.coordinator("salon") is cuisine


def test_removing_another_speaker_changes_nothing_and_a_lone_speaker_stays_itself():
    salon, cuisine, bain = Zone("salon"), Zone("cuisine"), Zone("bain")
    regroup(salon, cuisine, bain)
    s = player(salon, cuisine, bain)
    s.coordinator("salon")
    regroup(salon, cuisine)
    regroup(bain)
    assert s.coordinator("salon") is salon
    seul = Zone("seul")
    regroup(seul)
    assert player(seul).coordinator("seul") is seul


def test_keeping_only_the_party_speaker_that_still_plays_keeps_the_party_on_it():
    """On retire les AUTRES enceintes ; celle de la soirée, seule, joue toujours : la soirée reste sur elle."""
    salon, cuisine = Zone("salon", playing=True), Zone("cuisine")
    regroup(salon, cuisine)
    s = player(salon, cuisine)
    s.coordinator("salon")
    regroup(salon)
    regroup(cuisine)
    assert s.coordinator("salon") is salon


def test_two_speakers_the_party_one_removed_the_other_keeps_playing_alone():
    salon, cuisine = Zone("salon"), Zone("cuisine", playing=True)
    regroup(salon, cuisine)
    s = player(salon, cuisine)
    s.coordinator("salon")
    regroup(salon)
    regroup(cuisine)
    assert [s.coordinator("salon") for _ in range(4)] == [cuisine] * 4  # et ça tient (rapport de l'agent cohérence)
