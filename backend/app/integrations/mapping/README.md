# Integration: Mapping

Adapter for geocoding and routing-distance providers used by `route_planning` and location lookups. No provider is selected yet; the choice, licence and cost are recorded in an ADR when the first routing feature starts.

**Status:** boundary defined only; nothing implemented.

Rules: integrations are called by module services, never by routers directly; they hold no business rules and no database tables of their own unless stated above.
