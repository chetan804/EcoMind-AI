import { render, screen, within } from '@testing-library/react';
import { DonutChart } from '@/components/data-display/DonutChart';
import { MetricTile } from '@/components/data-display/MetricTile';
import { visibleLabelIndexes } from '@/components/data-display/chart-labels';
import { TrendChart } from '@/components/data-display/TrendChart';

describe('TrendChart', () => {
  const props = {
    unit: 'kg per day',
    ariaLabel: 'Waste trend',
    xLabels: ['Mon', 'Tue', 'Wed'],
    series: [
      { id: 'obs', label: 'Observed', color: 'red', values: [10, 20, 30] },
      { id: 'fc', label: 'Forecast', color: 'blue', values: [null, 22, 28] },
    ],
  };

  it('names the chart with its unit, shows a legend, and exposes the data as a table', () => {
    render(<TrendChart {...props} />);
    expect(screen.getByRole('img', { name: 'Waste trend (kg per day)' })).toBeInTheDocument();
    const legend = screen.getByRole('list');
    expect(within(legend).getByText('Observed')).toBeInTheDocument();
    expect(within(legend).getByText('Forecast')).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Waste trend (kg per day)' });
    expect(within(table).getByRole('row', { name: /Mon\s+10\s+no data/ })).toBeInTheDocument();
    expect(within(table).getByRole('row', { name: /Wed\s+30\s+28/ })).toBeInTheDocument();
  });

  it('shows an honest empty state when no series has data', () => {
    render(<TrendChart {...props} series={[{ id: 'a', label: 'A', color: 'red', values: [null, null, null] }]} emptyMessage="No readings yet." />);
    expect(screen.getByText('No readings yet.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});

describe('DonutChart', () => {
  it('lists every segment label and share in an accessible legend', () => {
    render(
      <DonutChart
        ariaLabel="Composition"
        segments={[
          { label: 'Organic', value: 60, color: 'green' },
          { label: 'Plastic', value: 40, color: 'blue' },
        ]}
      />,
    );
    const list = screen.getByRole('list', { name: 'Composition' });
    expect(within(list).getByText('Organic')).toBeInTheDocument();
    expect(within(list).getByText('60%')).toBeInTheDocument();
    expect(within(list).getByText('40%')).toBeInTheDocument();
  });
});

describe('MetricTile', () => {
  it('renders label, value and note', () => {
    render(<MetricTile icon={<span />} label="Collected" value="12 kg" note="demo" />);
    expect(screen.getByText('12 kg')).toBeInTheDocument();
    expect(screen.getByText('Collected')).toBeInTheDocument();
  });
});

describe('visibleLabelIndexes', () => {
  const labels = (n: number) => Array.from({ length: n }, (_, i) => `W${i}`);

  it('keeps every label when they fit', () => {
    expect(visibleLabelIndexes(labels(5), 800)).toEqual([0, 1, 2, 3, 4]);
  });

  it('thins crowded labels evenly but always keeps the first and the last', () => {
    const picked = visibleLabelIndexes(labels(60), 800);
    expect(picked[0]).toBe(0);
    expect(picked[picked.length - 1]).toBe(59);
    expect(picked.length).toBeLessThanOrEqual(Math.floor(800 / 72) + 1);
    const gaps = picked.slice(1).map((v, i) => v - (picked[i] ?? 0));
    expect(Math.min(...gaps)).toBeGreaterThan(1);
  });
});
