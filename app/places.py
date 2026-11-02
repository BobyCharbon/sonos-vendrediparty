"""Recherche de lieux dans Google Maps pour l'assistant IA : plusieurs lieux possibles, la personne choisit le bon.
Deux API, selon ce que l'IA a compris du lieu :
- une adresse de particulier (« chez moi, 420 route des Rosselets, Ségny ») → API Geocoding, qui trouve des ADRESSES ;
  la recherche d'établissements renverrait les commerces voisins (cordonnerie, mairie…) ;
- un établissement (bar, restaurant, salle, entreprise) → API Places « Text Search », qui trouve des LIEUX nommés.
Sans GOOGLE_MAPS_API_KEY, rien n'est cherché ici : l'app cherche alors dans les Plans d'Apple, et la personne choisit
de la même façon. La clé doit avoir les deux API activées (Places API (New) et Geocoding API)."""
import logging

import httpx

from .accounts import AccountError

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.googleMapsUri,places.types"
MAX_RESULTS = 5
MAX_QUERY = 200
MAX_CHOICES = 8
# Un résultat Google qui EST une adresse (et non un commerce situé à cette adresse).
ADDRESS_TYPES = {"street_address", "premise", "subpremise", "route", "street_number", "plus_code"}
EXACT_LOCATIONS = {"ROOFTOP", "RANGE_INTERPOLATED"}  # numéro trouvé ; sinon la rue ou la localité seulement

log = logging.getLogger(__name__)


def _clean(query: str) -> str:
    return " ".join(str(query or "").split())[:MAX_QUERY]


def maps_link(query: str) -> str:
    return str(httpx.URL("https://www.google.com/maps/search/", params={"api": "1", "query": query}))


class Places:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key.strip()
        self.client = client or httpx.Client(timeout=10)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[dict]:
        """« Bar Les Sbires, Ferney-Voltaire » → jusqu'à 5 lieux : nom, adresse, position et lien Google Maps."""
        query = _clean(query)
        if not query or not self.configured:
            return []
        try:
            r = self.client.post(SEARCH_URL, json={"textQuery": query, "languageCode": "fr", "regionCode": "CH",
                                                   "maxResultCount": MAX_RESULTS},
                                 headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELDS})
        except httpx.HTTPError as e:
            raise AccountError("Google Maps ne répond pas. Réessaie dans un instant.") from e
        if r.status_code != 200:
            raise AccountError("La recherche Google Maps n'a pas marché.")
        found = []
        for p in (r.json().get("places") or [])[:MAX_RESULTS]:
            where = p.get("location") or {}
            url = str(p.get("googleMapsUri") or "")
            types = {str(t) for t in p.get("types") or []}
            found.append({"name": str((p.get("displayName") or {}).get("text") or "")[:120],
                          "address": str(p.get("formattedAddress") or "")[:300],
                          "latitude": float(where.get("latitude") or 0), "longitude": float(where.get("longitude") or 0),
                          "url": url if url.startswith("https://") else "",
                          "is_address": bool(types & ADDRESS_TYPES), "exact": True})
        return [p for p in found if p["name"] or p["address"]]

    def geocode(self, query: str) -> list[dict]:
        """« 420 route des Rosselets, 01170 Ségny » → les adresses correspondantes ; « exact » quand le numéro est
        trouvé, sinon la rue ou la localité (approchée). Vide si l'API Geocoding n'est pas activée pour la clé."""
        query = _clean(query)
        if not query or not self.configured:
            return []
        try:
            r = self.client.get(GEOCODE_URL, params={"address": query, "language": "fr", "region": "ch",
                                                     "key": self.api_key})
        except httpx.HTTPError as e:
            raise AccountError("Google Maps ne répond pas. Réessaie dans un instant.") from e
        body = r.json() if r.status_code == 200 else {}
        status = body.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            # Clé sans l'API Geocoding, quota… : la recherche d'établissements prend le relais, l'admin le voit au journal.
            log.warning("Google Geocoding indisponible (%s) : %s", status or r.status_code, body.get("error_message", ""))
            return []
        found = []
        for g in (body.get("results") or [])[:MAX_RESULTS]:
            address = str(g.get("formatted_address") or "")[:300]
            geometry = g.get("geometry") or {}
            where = geometry.get("location") or {}
            if not address:
                continue
            found.append({"name": address.split(",")[0][:120], "address": address,
                          "latitude": float(where.get("lat") or 0), "longitude": float(where.get("lng") or 0),
                          "url": maps_link(address), "is_address": True,
                          "exact": geometry.get("location_type") in EXACT_LOCATIONS and not g.get("partial_match")})
        return found

    def search_all(self, queries: list[str]) -> list[dict]:
        """Le lieu tel que dit, puis une recherche plus large (type de lieu et ville) : un nom mal dicté (« Zoubir »)
        ne trouve rien, mais « bar techno, Ferney-Voltaire » fait sortir le bon (S'Beer). Sans doublon, 8 au plus."""
        return _merge(p for q in [q for q in queries if str(q or "").strip()][:3] for p in self.search(q))

    def find(self, query: str, broad: str, kind: str) -> list[dict]:
        """Lieux possibles selon ce que l'IA a compris : une adresse de particulier ne propose que des adresses
        (exactes d'abord), jamais les commerces voisins ; un établissement passe par la recherche de lieux nommés."""
        if kind != "home":
            return self.search_all([query, broad])
        found = self.geocode(query) + [p for p in self.search(query) if p["is_address"]]
        return _merge(sorted(found, key=lambda p: not p["exact"]))


def _merge(places) -> list[dict]:
    seen, merged = set(), []
    for p in places:
        key = (p["name"].lower(), p["address"].lower())
        if key not in seen:
            seen.add(key)
            merged.append(p)
    return merged[:MAX_CHOICES]
