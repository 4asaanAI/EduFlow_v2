"""Google Maps API helpers for transport optimisation (Story 7-46)."""

from __future__ import annotations

import math
import logging

import httpx

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_TIMEOUT = 5.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


async def geocode(address: str, api_key: str) -> dict:
    """Geocode an address string to lat/lng using the Google Maps Geocoding API.

    Returns {"lat": float, "lng": float, "formatted_address": str}.
    Raises RuntimeError("geocode_failed") on any API or network error.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _GEOCODE_URL, params={"address": address, "key": api_key}
            )
        data = resp.json()
    except Exception:
        logger.warning("geocode network error address=%r", address, exc_info=True)
        raise RuntimeError("geocode_failed")

    if data.get("status") != "OK" or not data.get("results"):
        logger.warning(
            "geocode api error status=%s address=%r", data.get("status"), address
        )
        raise RuntimeError("geocode_failed")

    result = data["results"][0]
    loc = result["geometry"]["location"]
    return {
        "lat": loc["lat"],
        "lng": loc["lng"],
        "formatted_address": result.get("formatted_address", address),
    }
