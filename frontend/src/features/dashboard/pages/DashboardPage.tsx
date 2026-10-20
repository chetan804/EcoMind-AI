import { Bell, Layers, Recycle, ScanSearch, TriangleAlert, Truck } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/Card';
import { DemoDataNotice } from '@/components/feedback/DemoDataNotice';
import { DonutChart } from '@/components/data-display/DonutChart';
import { Legend } from '@/components/data-display/Legend';
import { MetricTile } from '@/components/data-display/MetricTile';
import { TrendChart } from '@/components/data-display/TrendChart';
import { PageHeader } from '@/components/layout/PageHeader';
import { Topbar } from '@/components/layout/Topbar';
import { DemoMap } from '../components/DemoMap';
import { mapLegend } from '../components/map-config';
import { demoAlerts, demoComposition, demoImpact, demoKpis, demoTrend } from '../fixtures/demo-overview';
import '../dashboard.css';

const kpiIcons = {
  collected: <Recycle size={28} />,
  diversion: <Layers size={28} />,
  points: <ScanSearch size={28} />,
  pending: <Truck size={28} />,
};

function greeting(date = new Date()): string {
  const hour = date.getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

/**
 * Operational command center layout. All figures come from demo fixtures (no analytics API yet);
 * the page says so in its header and each data region is covered by the notice.
 */
export function DashboardPage() {
  return (
    <>
      <Topbar />
      <PageHeader
        title={greeting()}
        subtitle="Operations overview"
        actions={<DemoDataNotice>Demonstration data, not live. No analytics service is connected.</DemoDataNotice>}
      />
      <div className="dash">
        <ul className="dash__kpis" aria-label="Key metrics (demonstration data)">
          {demoKpis.map((kpi) => (
            <li key={kpi.id}>
              <Card className="dash__kpi">
                <MetricTile icon={kpiIcons[kpi.id]} tone={kpi.tone} label={kpi.label} value={kpi.value} />
              </Card>
            </li>
          ))}
        </ul>

        <div className="dash__row dash__row--main">
          <Card className="dash__chart-card" aria-labelledby="trend-title">
            <CardHeader title="Waste generation trend" titleId="trend-title" actions={<span className="dash__range">Last 7 days</span>} />
            <TrendChart
              height={195}
              unit={demoTrend.unit}
              xLabels={[...demoTrend.xLabels]}
              ariaLabel="Waste generation trend, observed and forecast (demonstration data)"
              series={[
                { id: 'observed', label: 'Observed', color: 'var(--color-teal)', values: [...demoTrend.observed], area: true },
                { id: 'forecast', label: 'Forecast', color: 'var(--color-info)', values: [...demoTrend.forecast], dashed: true },
              ]}
            />
          </Card>

          <Card className="dash__map-card" aria-labelledby="map-title">
            <CardHeader title="City map" titleId="map-title" actions={<DemoDataNotice>Sample layout</DemoDataNotice>} />
            <div className="dash__map">
              <DemoMap />
              <div className="dash__map-legend">
                <Legend variant="dots" items={mapLegend} />
              </div>
            </div>
          </Card>
        </div>

        <div className="dash__row dash__row--summary">
          <Card aria-labelledby="alerts-title">
            <CardHeader title="Critical alerts" titleId="alerts-title" />
            <ul className="alert-list">
              {demoAlerts.map((alert) => (
                <li key={alert.id} className="alert-row">
                  <span className={`alert-row__icon alert-row__icon--${alert.severity}`} aria-hidden="true">
                    {alert.severity === 'danger' ? <TriangleAlert size={20} /> : <Bell size={20} />}
                  </span>
                  <span className="alert-row__title">{alert.title}</span>
                  <span className="alert-row__when">{alert.when}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card aria-labelledby="composition-title">
            <CardHeader title="Waste composition" titleId="composition-title" />
            <DonutChart ariaLabel="Waste composition by share (demonstration data)" segments={demoComposition.map((s) => ({ ...s }))} />
          </Card>

          <Card aria-labelledby="impact-title">
            <CardHeader title="Environmental impact" titleId="impact-title" />
            <p className="impact__value">
              {demoImpact.value}
              <span className="impact__unit">{demoImpact.unit}</span>
            </p>
            <p className="impact__label">{demoImpact.label}</p>
          </Card>
        </div>
      </div>
    </>
  );
}
