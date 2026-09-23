/* Unit tests for pure frontend helpers. */

import { describe, expect, it } from 'vitest'
import { fmtKg, fmtNumber, fmtPct, humanize, statusColor, timeAgo } from '../src/lib/format'

describe('fmtNumber', () => {
  it('formats integers with thousands separators', () => {
    expect(fmtNumber(1234567)).toBe('1,234,567')
  })
  it('respects digit count', () => {
    expect(fmtNumber(1234.567, 2)).toBe('1,234.57')
  })
  it('handles null/undefined', () => {
    expect(fmtNumber(null)).toBe('—')
    expect(fmtNumber(undefined)).toBe('—')
  })
})

describe('fmtKg', () => {
  it('renders under a tonne in kg', () => {
    expect(fmtKg(850)).toBe('850 kg')
  })
  it('renders >= 1000 kg in tonnes', () => {
    expect(fmtKg(27254.4)).toBe('27.3 t')
  })
  it('handles null', () => {
    expect(fmtKg(null)).toBe('—')
  })
})

describe('fmtPct', () => {
  it('formats a fraction as a percentage', () => {
    expect(fmtPct(0.6551, 1)).toBe('65.5%')
    expect(fmtPct(0.6551, 0)).toBe('66%')
  })
  it('handles null', () => {
    expect(fmtPct(null)).toBe('—')
  })
})

describe('humanize', () => {
  it('turns snake_case into title case', () => {
    expect(humanize('in_progress')).toBe('In Progress')
    expect(humanize('field_supervisor')).toBe('Field Supervisor')
  })
  it('handles plain words', () => {
    expect(humanize('resolved')).toBe('Resolved')
  })
})

describe('statusColor', () => {
  it('maps completion tones to emerald', () => {
    expect(statusColor('completed')).toContain('emerald')
    expect(statusColor('resolved')).toContain('emerald')
  })
  it('maps failure tones to rose', () => {
    expect(statusColor('rejected')).toContain('rose')
    expect(statusColor('failed')).toContain('rose')
  })
  it('maps missed/skipped to amber', () => {
    expect(statusColor('missed')).toContain('amber')
  })
  it('falls back to neutral for unknown statuses', () => {
    expect(statusColor('something_new')).toContain('slate')
  })
})

describe('timeAgo', () => {
  it('renders compact relative times', () => {
    const now = Date.now()
    expect(timeAgo(new Date(now - 30_000).toISOString())).toBe('just now')
    expect(timeAgo(new Date(now - 5 * 60_000).toISOString())).toBe('5m ago')
    expect(timeAgo(new Date(now - 3 * 3_600_000).toISOString())).toBe('3h ago')
    expect(timeAgo(new Date(now - 2 * 86_400_000).toISOString())).toBe('2d ago')
  })
  it('handles null', () => {
    expect(timeAgo(null)).toBe('—')
  })
})
