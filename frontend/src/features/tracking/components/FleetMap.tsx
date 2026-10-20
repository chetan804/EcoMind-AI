import { useMemo, useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Checkbox } from '@/components/ui/Choice';
import { useFacilityOptions } from '@/features/facilities';
import { facilityMarkers, MapPanel, type LegendEntry } from '@/features/maps';
import { useAuth } from '@/services/session';
import { formatDateTime } from '@/utils/format';
import { POLL_MS, useLatestPositions } from '../hooks/useTracking';
import { vehicleMarkers } from '../markers';

const LEGEND: LegendEntry[] = [
  { key: 'live', label: 'LIVE GPS (recent report from a real source)', tone: 'success' },
  { key: 'delayed', label: 'DELAYED', tone: 'warning' },
  { key: 'stale', label: 'STALE (no recent report)', tone: 'danger' },
  { key: 'simulated', label: 'SIMULATED (demonstration data)', tone: 'simulated' },
  { key: 'facility', label: 'Facility or depot (fixed location, not a vehicle)', tone: 'info' },
];

/**
 * Where the vehicles are, according to the position reports the server received, with facilities
 * as fixed reference points. A vehicle that never reported has no marker and is listed under the
 * map as LOCATION UNAVAILABLE; a database coordinate is never drawn as a vehicle.
 */
export function FleetMap({ height = 420, showFacilities = true, defaultSimulated = false }: { height?: number; showFacilities?: boolean; defaultSimulated?: boolean }) {
  const { can } = useAuth();
  const [layers, setLayers] = useState({ vehicles: true, facilities: showFacilities, simulated: defaultSimulated });
  const positions = useLatestPositions(can('fleet:read'), layers.simulated);
  const facilities = useFacilityOptions(showFacilities && can('facilities:read'));

  const rows = useMemo(() => positions.data?.items ?? [], [positions.data]);
  const markers = useMemo(
    () => [...(layers.vehicles ? vehicleMarkers(rows.filter((r) => layers.simulated || !r.simulated)) : []), ...(layers.facilities ? facilityMarkers(facilities.data ?? []) : [])],
    [rows, facilities.data, layers],
  );
  const unavailable = rows.filter((r) => !r.simulated && r.position === null);

  return (
    <div className="stack stack--tight">
      <fieldset className="filter-bar" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="visually-hidden">Map layers</legend>
        <Checkbox label="Vehicles" checked={layers.vehicles} onChange={(e) => setLayers((l) => ({ ...l, vehicles: e.target.checked }))} />
        {showFacilities && (
          <Checkbox label="Facilities and depots" checked={layers.facilities} onChange={(e) => setLayers((l) => ({ ...l, facilities: e.target.checked }))} />
        )}
        <Checkbox label="Simulated vehicles" checked={layers.simulated} onChange={(e) => setLayers((l) => ({ ...l, simulated: e.target.checked }))} />
      </fieldset>
      {positions.isError && (
        <Alert tone="warning" title="Vehicle positions could not be refreshed">
          The map shows the last positions received; this view retries automatically with a growing delay.
        </Alert>
      )}
      <MapPanel
        label="Fleet positions"
        markers={markers}
        legend={LEGEND}
        height={height}
        emptyMessage="No vehicle has reported a position yet."
        footer={
          <p className="map-panel__note">
            {positions.data
              ? `Positions as of ${formatDateTime(positions.data.generated_at)}; refreshed every ${POLL_MS / 1000} s while this tab is open. LIVE means reported within ${positions.data.live_within_seconds} s by a real source; STALE means older than ${Math.round(positions.data.stale_after_seconds / 60)} min.`
              : positions.isPending
                ? 'Loading positions…'
                : 'Positions are unavailable.'}
            {unavailable.length > 0 && ` LOCATION UNAVAILABLE (never reported): ${unavailable.map((r) => r.registration_number).join(', ')}.`}
          </p>
        }
      />
    </div>
  );
}
