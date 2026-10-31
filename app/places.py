"""Recherche de lieux dans Google Maps (API Google Places, « Text Search ») pour l'assistant IA : plusieurs lieux
possibles, la personne choisit le bon. Sans GOOGLE_MAPS_API_KEY, rien n'est cherché ici : l'app cherche alors dans
les Plans d'Apple, et la personne choisit de la même façon."""
import httpx

from .accounts import AccountError

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.googleMapsUri"
MAX_RESULTS = 5
MAX_QUERY = 200


class Places:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key.strip()
        self.client = client or httpx.Client(timeout=10)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[dict]:
        """« Bar Les Sbires, Ferney-Voltaire » → jusqu'à 5 lieux : nom, adresse, position et lien Google Maps."""
        query = " ".join(str(query or "").split())[:MAX_QUERY]
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
            found.append({"name": str((p.get("displayName") or {}).get("text") or "")[:120],
                          "address": str(p.get("formattedAddress") or "")[:300],
                          "latitude": float(where.get("latitude") or 0), "longitude": float(where.get("longitude") or 0),
                          "url": url if url.startswith("https://") else ""})
        return [p for p in found if p["name"] or p["address"]]
