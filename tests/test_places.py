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


# Retour du 02.11 : « 420 route des Rosselets, 01170 Ségny » (soirée chez soi) proposait une cordonnerie, une auberge
# et la mairie de Ségny : la recherche d'établissements renvoie les commerces voisins d'une adresse qu'elle ne connaît pas.
SEGNY_SHOPS = {"places": [
    {"displayName": {"text": "Cordonnerie Multiservice Bes Service"}, "formattedAddress": "5 Route nationale, 01170 Ségny",
     "location": {"latitude": 46.29, "longitude": 6.07}, "types": ["shoe_store", "point_of_interest", "establishment"]},
    {"displayName": {"text": "Mairie de Ségny"}, "formattedAddress": "103 Rue du Vieux Bourg, 01170 Ségny",
     "location": {"latitude": 46.29, "longitude": 6.07}, "types": ["city_hall", "point_of_interest", "establishment"]},
]}
SEGNY_STREET = {"status": "OK", "results": [
    {"formatted_address": "Route des Rosselets, 01170 Ségny, France", "partial_match": True,
     "geometry": {"location": {"lat": 46.295, "lng": 6.071}, "location_type": "GEOMETRIC_CENTER"}},
    {"formatted_address": "420 Route des Rosselets, 01170 Ségny, France",
     "geometry": {"location": {"lat": 46.296, "lng": 6.072}, "location_type": "ROOFTOP"}},
]}


def google(geocode_answer, places_answer=SEGNY_SHOPS, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        if "geocode" in request.url.path:
            return httpx.Response(200, json=geocode_answer)
        return httpx.Response(200, json=places_answer)
    return Places("k", client(handler))


def test_a_home_address_only_offers_addresses_exact_first_never_the_neighbouring_shops():
    seen = []
    found = google(SEGNY_STREET, seen=seen).find("420 Route des Rosselets, 01170 Ségny, France", "", "home")
    assert [p["address"] for p in found] == ["420 Route des Rosselets, 01170 Ségny, France",
                                             "Route des Rosselets, 01170 Ségny, France"]
    assert found[0]["exact"] and not found[1]["exact"]
    assert found[0]["url"].startswith("https://www.google.com/maps/search/?api=1&query=420")
    geo = next(r for r in seen if "geocode" in r.url.path)
    assert geo.url.params["key"] == "k" and geo.url.params["address"].startswith("420 Route des Rosselets")


def test_a_home_address_unknown_to_google_offers_nothing_rather_than_shops():
    assert google({"status": "ZERO_RESULTS", "results": []}).find("420 Route des Rosselets, Ségny", "", "home") == []


def test_a_key_without_the_geocoding_api_still_offers_real_addresses_from_places():
    answer = {"places": SEGNY_SHOPS["places"] + [
        {"displayName": {"text": "420 Route des Rosselets"}, "formattedAddress": "420 Route des Rosselets, 01170 Ségny",
         "location": {"latitude": 46.296, "longitude": 6.072}, "types": ["street_address"]}]}
    found = google({"status": "REQUEST_DENIED", "error_message": "API not enabled"}, answer).find("420 Route des Rosselets", "", "home")
    assert [p["name"] for p in found] == ["420 Route des Rosselets"]


def test_a_venue_is_still_searched_among_named_places_with_the_broader_search():
    seen = []
    found = google(SEGNY_STREET, ANSWER, seen).find("Les Sbires, Ferney", "bar, Ferney-Voltaire", "venue")
    assert [p["name"] for p in found] == ["Les Sbires", "Bar Voltaire"]
    assert not any("geocode" in r.url.path for r in seen)
