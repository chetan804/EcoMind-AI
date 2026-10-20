import { useMemo } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { MapPanel, toPoint, type MapMarker, type MapPath } from '@/features/maps';
import { useCollectionTracking } from '../hooks/useTracking';
import { vehicleMarkers } from '../markers';
import { VehicleStatusBadge } from './VehicleStatusBadge';
import type { CollectionTracking } from '../api/tracking-api';

function Body({ data }: { data: CollectionTracking }) {
  const { markers, paths } = useMemo(() => {
    const m: MapMarker[] = [];
    const task = toPoint(data.latitude, data.longitude);
    if (task) {
      m.push({
        id: 'task',
        position: task,
        title: data.title,
        kind: 'task',
        tone: data.status === 'completed' ? 'success' : data.status === 'failed' ? 'danger' : 'info',
        glyph: '●',
        statusLabel: `Task ${data.status.replace('_', ' ')}`,
        details: ['Collection point'],
      });
    }
    if (data.vehicle) m.push(...vehicleMarkers([data.vehicle]));
    const recorded = data.path.flatMap((p) => {
      const point = toPoint(p.latitude, p.longitude);
      return point ? [point] : [];
    });
    const p: MapPath[] = recorded.length >= 2 ? [{ id: 'recorded', kind: 'recorded', points: recorded, label: 'Recorded vehicle path for this task' }] : [];
    return { markers: m, paths: p };
  }, [data]);

  return (
    <div className="stack stack--tight">
      {data.vehicle ? (
        <p>
          Vehicle {data.vehicle.registration_number}: <VehicleStatusBadge status={data.vehicle.status} />
        </p>
      ) : (
        <Alert tone="info">No vehicle is assigned to this task, so there is nothing to track.</Alert>
      )}
      {data.vehicle && data.path.length === 0 && (
        <Alert tone="info">No positions have been linked to this task yet. A path appears when the assigned collector&apos;s device reports positions while the task is in progress.</Alert>
      )}
      <MapPanel
        label="Collection tracking"
        markers={markers}
        paths={paths}
        height={300}
        legend={[
          { key: 'task', label: 'Collection point (planned location)', tone: 'info' },
          { key: 'path', label: 'Recorded path (positions received, not a navigation route)', pathKind: 'recorded' },
          { key: 'veh', label: 'Vehicle (status shown in its label)', tone: 'success' },
        ]}
        footer={<p className="map-panel__note">{data.basis}</p>}
      />
    </div>
  );
}

/** Planned location, vehicle position and recorded path for one collection task. */
export function CollectionTrackMap({ taskId }: { taskId: string }) {
  const query = useCollectionTracking(taskId, true);
  return (
    <QueryBoundary query={query} label="collection tracking">
      {(data) => <Body data={data} />}
    </QueryBoundary>
  );
}
