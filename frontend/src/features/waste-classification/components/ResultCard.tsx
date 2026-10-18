import { useId } from 'react';
import { Droplets, ScanSearch } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { DemoDataNotice } from '@/components/feedback/DemoDataNotice';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { sampleResult } from '../fixtures/sample-layout';

export type ResultView =
  | { kind: 'empty' }
  | { kind: 'unavailable'; fileName: string }
  | { kind: 'sample' };

/**
 * The classification result panel. There is no classification service or model yet, so a real
 * upload ends in the `unavailable` state. `sample` renders the layout with a labelled sample.
 */
export function ResultCard({ view, onReset }: { view: ResultView; onReset: () => void }) {
  const titleId = useId();
  return (
    <Card aria-labelledby={titleId} className="result">
      <CardHeader title="Classification result" titleId={titleId} actions={view.kind === 'sample' ? <DemoDataNotice>Sample layout</DemoDataNotice> : undefined} />

      {view.kind === 'empty' && (
        <EmptyState icon={<ScanSearch size={24} />} title="No image yet" description="Choose an image to begin. Results will appear here once classification is available." />
      )}

      {view.kind === 'unavailable' && (
        <div className="result__stack">
          <Alert tone="warning" title="Classification is not available yet">
            The classification service is not implemented and no model has been trained, so “{view.fileName}” was
            checked and previewed locally but not analysed. Nothing was uploaded.
          </Alert>
          <Button variant="secondary" onClick={onReset}>
            Try another image
          </Button>
        </div>
      )}

      {view.kind === 'sample' && (
        <div className="result__stack">
          <div className="result__class">
            <span className="result__tile" aria-hidden="true">
              <Droplets size={36} />
            </span>
            <div>
              <p className="result__name">{sampleResult.className}</p>
              <p className="result__caption">Sample output for layout review, not a model result</p>
            </div>
          </div>
          <ProgressBar label="Confidence bar (sample, not a measurement)" value={sampleResult.fill * 100} />
          <dl className="result__facts">
            <div><dt>Model</dt><dd>Not connected</dd></div>
            <div><dt>Evaluation</dt><dd>Not evaluated</dd></div>
            <div><dt>Source</dt><dd>Sample illustration</dd></div>
          </dl>
          <div className="result__actions">
            <Button unavailableReason="Review needs the classification service, which is not built yet.">Verify result</Button>
            <Button variant="secondary" onClick={onReset}>
              Try another image
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
