/** Public interface of the tracking feature (vehicle positions, freshness labels, simulator). */
export { FleetMap } from './components/FleetMap';
export { CollectionTrackMap } from './components/CollectionTrackMap';
export { SimulationControls } from './components/SimulationControls';
export { VehicleStatusBadge } from './components/VehicleStatusBadge';
export { useLatestPositions, useRouteTracking, useTrackingConfig, pollingInterval } from './hooks/useTracking';
export { vehicleMarkers } from './markers';
export { STATUS_LABEL, formatAge } from './labels';
export type { RouteTracking, TrackingStatus, VehiclePosition } from './api/tracking-api';
