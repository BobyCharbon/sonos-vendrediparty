"""Lieux Google Maps pour l'assistant IA : plusieurs possibilités lisibles, rien sans clé, erreurs claires."""
import httpx
import pytest

from app.accounts import AccountError
from app.places import Places

ANSWER = {"places": [
    {"id": "a", "displayName": {"text": "Les Sbires"}, "formattedAddress": "9 Rue de Genève, 01210 Ferney-Voltaire, France",
     "location": {"latitude": 46.256, "longitude": 6.108}, "googleMapsUri": "https://maps.google.com/?cid=1"},
    {"id": "b", "displayName": {"text": "Bar Voltaire"}, "formattedAddress": "Avenue Voltaire, 01210 Ferney-Voltaire",
     "location": {"latitude": 46.25, "longitude": 6.11}, "googleMapsUri": "javascript:alert(1)"},
]}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_google_gives_several_places_with_their_exact_link():
    seen = {}

    def handler(request):
        seen["key"] = request.headers["X-Goog-Api-Key"]
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=ANSWER)

    found = Places("cle-test", client(handler)).search("bar les sbires ferney voltaire")
    assert [p["name"] for p in found] == ["Les Sbires", "Bar Voltaire"]
    assert found[0]["address"].startswith("9 Rue de Genève") and found[0]["url"] == "https://maps.google.com/?cid=1"
    assert found[1]["url"] == ""  # lien non https refusé
    assert seen["key"] == "cle-test" and '"regionCode":"CH"' in seen["body"].replace(" ", "")


def test_without_key_nothing_is_asked_to_google():
    assert Places("", client(lambda r: pytest.fail("appel inattendu"))).search("Fun Planet") == []


def test_google_errors_are_explained():
    with pytest.raises(AccountError, match="Google Maps"):
        Places("k", client(lambda r: httpx.Response(403, json={}))).search("Fun Planet")


def test_a_badly_dictated_name_still_finds_the_place_through_the_broader_search():
    def handler(request):
        body = request.read().decode()
        if "Zoubir" in body:
            return httpx.Response(200, json={})
        return httpx.Response(200, json=ANSWER)

    found = Places("k", client(handler)).search_all(["Zoubir, Ferney-Voltaire", "bar techno, Ferney-Voltaire", ""])
    assert [p["name"] for p in found] == ["Les Sbires", "Bar Voltaire"]


def test_both_searches_are_merged_without_duplicates():
    found = Places("k", client(lambda r: httpx.Response(200, json=ANSWER))).search_all(["a", "b"])
    assert len(found) == 2
