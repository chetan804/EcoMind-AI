import { useEffect, useRef, useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime } from '@/utils/format';
import { useReportLocation } from '../hooks/useTracking';

/** At most one report per this many milliseconds; the server allows far more, this keeps traffic and battery use low. */
export const SHARE_INTERVAL_MS = 15_000;

type Phase = 'idle' | 'requesting' | 'sharing' | 'denied' | 'unavailable';

/**
 * Lets the assigned collector send this device's position while a task is in progress. It is a
 * real source (`mobile_client`): positions come from the browser's Geolocation API, only after the
 * user presses the button and the browser grants permission, only while this page is open.
 */
export function LocationSharing({ vehicleId, taskId }: { vehicleId: string; taskId: string }) {
  const { can } = useAuth();
  const report = useReportLocation();
  const send = report.mutate;
  const [phase, setPhase] = useState<Phase>('idle');
  const [sentAt, setSentAt] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [failure, setFailure] = useState<string | null>(null);
  const watchId = useRef<number | null>(null);
  const lastSent = useRef(0);

  const stop = () => {
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    watchId.current = null;
    setPhase('idle');
  };
  useEffect(
    () => () => {
      if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    },
    [],
  );

  if (!can('fleet:track')) return null;

  const onPosition = (position: GeolocationPosition) => {
    setPhase('sharing');
    const now = Date.now();
    if (now - lastSent.current < SHARE_INTERVAL_MS) return;
    lastSent.current = now;
    const { latitude, longitude, accuracy, speed, heading } = position.coords;
    send(
      {
        vehicleId,
        body: {
          latitude: latitude.toFixed(6),
          longitude: longitude.toFixed(6),
          recorded_at: new Date(position.timestamp).toISOString(),
          source: 'mobile_client',
          accuracy_m: Number.isFinite(accuracy) ? accuracy.toFixed(2) : undefined,
          // The browser reports m/s; speed and heading are sent only when the device measured them.
          speed_kph: speed !== null && Number.isFinite(speed) ? (speed * 3.6).toFixed(2) : undefined,
          heading_deg: heading !== null && Number.isFinite(heading) ? (((heading % 360) + 360) % 360).toFixed(2) : undefined,
          collection_task_id: taskId,
        },
      },
      {
        onSuccess: () => {
          setFailure(null);
          setSentAt(new Date().toISOString());
          setCount((c) => c + 1);
        },
        onError: (error) => setFailure(getErrorMessage(error)),
      },
    );
  };
  const onError = (error: GeolocationPositionError) => {
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    watchId.current = null;
    setPhase(error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable');
  };
  const start = () => {
    if (!('geolocation' in navigator)) {
      setPhase('unavailable');
      return;
    }
    setFailure(null);
    setPhase('requesting');
    lastSent.current = 0;
    watchId.current = navigator.geolocation.watchPosition(onPosition, onError, { enableHighAccuracy: true, maximumAge: 5000, timeout: 20_000 });
  };

  const active = phase === 'requesting' || phase === 'sharing';
  return (
    <section aria-label="Share position" className="stack stack--tight">
      <h4>Share my position</h4>
      <p className="muted">
        Sends this device&apos;s location to the fleet record of the assigned vehicle while this page stays open. Nothing is sent until you press the button and your browser allows it; closing this page stops it.
      </p>
      <div className="row-actions">
        {active ? <Button variant="secondary" onClick={stop}>Stop sharing</Button> : <Button onClick={start}>Share my position</Button>}
        <span role="status" aria-live="polite">
          {phase === 'requesting' && 'Waiting for your browser to provide a position…'}
          {phase === 'sharing' && (sentAt ? `Sharing. ${count} report${count === 1 ? '' : 's'} sent, last at ${formatDateTime(sentAt)}.` : 'Sharing. First report is being sent…')}
        </span>
      </div>
      {phase === 'denied' && <Alert tone="warning">Location permission was denied, so nothing is being shared. Allow location for this site in your browser to try again.</Alert>}
      {phase === 'unavailable' && <Alert tone="warning">This device could not provide a position, so nothing is being shared.</Alert>}
      {failure && <Alert tone="danger" title="A position report was not accepted">{failure}</Alert>}
    </section>
  );
}
