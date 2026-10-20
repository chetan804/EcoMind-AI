"""Choose the road-routing provider from settings (``ROUTING_PROVIDER``)."""

from __future__ import annotations

from app.core.config import Settings
from app.integrations.mapping.base import RoadRouteProvider
from app.integrations.mapping.google_routes import GoogleRoutesProvider
from app.integrations.mapping.osrm import OsrmProvider


def build_road_route_provider(settings: Settings) -> RoadRouteProvider:
    choice = settings.effective_routing_provider
    if choice == "osrm":
        return OsrmProvider(settings.osrm_base_url, timeout_seconds=settings.osrm_timeout_seconds)
    # "google", and "none" (a Google provider without a key answers "not_configured").
    key = settings.google_maps_server_api_key if choice == "google" else None
    return GoogleRoutesProvider(key, timeout_seconds=settings.google_routes_timeout_seconds)
