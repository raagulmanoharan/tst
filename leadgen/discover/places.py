"""Google Places (New) client.

The whole file is shaped by one constraint: Places data may drive a run but may
not be written to disk. So discovery returns `place_id`s, and everything else
arrives through `EphemeralPlace`, which is a plain dataclass with no
serialisation helpers — deliberately awkward to persist. See CLAUDE.md rule 3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

from ..config import (
    BUDGET_STOP_RATIO,
    BUDGET_WARN_RATIO,
    SKU_BUDGETS,
    CategoryProbe,
    City,
    Settings,
)
from ..store import LeadStore

log = logging.getLogger(__name__)

BASE_URL = "https://places.googleapis.com/v1"

# Field masks decide the billing SKU: the highest-tier field requested sets the
# tier for the whole call. Keep these two masks separate and minimal.
DISCOVERY_MASK = "places.id,places.location"
DISCOVERY_SKU = "text_search_pro"

DETAILS_MASK = (
    "id,displayName,formattedAddress,nationalPhoneNumber,"
    "websiteUri,rating,userRatingCount,primaryTypeDisplayName"
)
DETAILS_SKU = "place_details_enterprise"


class BudgetExceeded(RuntimeError):
    """Raised before a call that would push past the free tier."""


class PlacesUnavailable(RuntimeError):
    """Raised when the API cannot be reached or refuses the request."""


@dataclass(slots=True)
class EphemeralPlace:
    """Google's view of a business, for this process only.

    Never persist this. Never construct a `PersistedModel` from it. It exists so
    that the verifier can find the business's own website and the dashboard can
    show a human-readable label — both at render time, from a live call.
    """

    place_id: str
    display_name: str | None = None
    formatted_address: str | None = None
    phone: str | None = None
    website_uri: str | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    primary_type: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> EphemeralPlace:
        display = payload.get("displayName") or {}
        primary = payload.get("primaryTypeDisplayName") or {}
        return cls(
            place_id=payload.get("id", ""),
            display_name=display.get("text"),
            formatted_address=payload.get("formattedAddress"),
            phone=payload.get("nationalPhoneNumber"),
            website_uri=payload.get("websiteUri"),
            rating=payload.get("rating"),
            user_rating_count=payload.get("userRatingCount"),
            primary_type=primary.get("text"),
        )

    @property
    def has_website(self) -> bool:
        return bool(self.website_uri)


@dataclass(slots=True)
class DiscoveredPlace:
    """The only thing discovery is allowed to hand onward."""

    place_id: str
    lat: float | None
    lng: float | None


class PlacesClient:
    def __init__(
        self,
        settings: Settings,
        store: LeadStore,
        client: httpx.Client | None = None,
    ) -> None:
        if not settings.api_key:
            raise PlacesUnavailable(
                "GOOGLE_MAPS_API_KEY is not set. Put it in .env (which is gitignored)."
            )
        self.settings = settings
        self.store = store
        self._client = client or httpx.Client(timeout=settings.request_timeout_s)

    def close(self) -> None:
        self._client.close()

    # -- budget -----------------------------------------------------------

    def _check_budget(self, sku: str, planned: int = 1) -> None:
        budget = SKU_BUDGETS.get(sku)
        if budget is None:
            return
        used = self.store.usage_this_month().get(sku, 0)
        if used + planned > budget.free_per_month * BUDGET_STOP_RATIO:
            raise BudgetExceeded(
                f"{sku}: {used} calls used this month against a {budget.free_per_month} "
                f"free allowance. Stopping at {BUDGET_STOP_RATIO:.0%} so this stays free. "
                f"Run `python -m leadgen budget` for detail."
            )
        if used + planned > budget.free_per_month * BUDGET_WARN_RATIO:
            log.warning(
                "%s at %d/%d of the monthly free tier", sku, used, budget.free_per_month
            )

    def _post(self, path: str, mask: str, body: dict[str, Any], sku: str) -> dict[str, Any]:
        self._check_budget(sku)
        try:
            response = self._client.post(
                f"{BASE_URL}/{path}",
                json=body,
                headers={
                    "X-Goog-Api-Key": self.settings.api_key or "",
                    "X-Goog-FieldMask": mask,
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise PlacesUnavailable(f"Places request failed: {exc}") from exc
        self.store.record_api_call(sku)
        if response.status_code != 200:
            raise PlacesUnavailable(
                f"Places returned {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    def _get(self, path: str, mask: str, sku: str) -> dict[str, Any]:
        self._check_budget(sku)
        try:
            response = self._client.get(
                f"{BASE_URL}/{path}",
                headers={
                    "X-Goog-Api-Key": self.settings.api_key or "",
                    "X-Goog-FieldMask": mask,
                },
            )
        except httpx.HTTPError as exc:
            raise PlacesUnavailable(f"Places request failed: {exc}") from exc
        self.store.record_api_call(sku)
        if response.status_code != 200:
            raise PlacesUnavailable(
                f"Places returned {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    # -- discovery --------------------------------------------------------

    def discover(
        self,
        city: City,
        probe: CategoryProbe,
        radius_m: float = 3000.0,
        max_centres: int | None = None,
    ) -> Iterable[DiscoveredPlace]:
        """Sweep a city grid for one category, yielding place_ids only."""
        centres = city.grid()
        if max_centres is not None:
            centres = centres[:max_centres]

        seen: set[str] = set()
        for lat, lng in centres:
            body = {
                "textQuery": f"{probe.query} in {city.name}",
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": radius_m,
                    }
                },
                "pageSize": 20,
            }
            try:
                payload = self._post("places:searchText", DISCOVERY_MASK, body, DISCOVERY_SKU)
            except BudgetExceeded:
                raise
            except PlacesUnavailable as exc:
                # One bad grid cell should not abandon the sweep.
                log.warning("grid cell (%s, %s) failed: %s", lat, lng, exc)
                continue

            for entry in payload.get("places", []):
                place_id = entry.get("id")
                if not place_id or place_id in seen:
                    continue
                seen.add(place_id)
                location = entry.get("location") or {}
                yield DiscoveredPlace(
                    place_id=place_id,
                    lat=location.get("latitude"),
                    lng=location.get("longitude"),
                )

    # -- live lookup ------------------------------------------------------

    def fetch_live(self, place_id: str) -> EphemeralPlace:
        """Fetch Google's current view of a place. In memory only, every time.

        This is the scarce SKU (7,000 free Enterprise calls a month), so callers
        should batch their work rather than looping over it casually.
        """
        payload = self._get(f"places/{place_id}", DETAILS_MASK, DETAILS_SKU)
        return EphemeralPlace.from_api(payload)
