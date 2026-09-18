# Route Optimization

The current route planner preserves a local nearest-neighbor fallback using validated coordinates. When `ROUTING_PROVIDER=osrm`, the planner requests road legs from `OSRM_BASE_URL` and falls back explicitly if OSRM is unavailable.

The project does not currently claim traffic-aware routing or OR-Tools optimization. Vehicle capacity, time windows, depots, working hours, multi-vehicle planning, route dates, and structured arrival estimates are future extensions.
