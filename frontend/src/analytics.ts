const ANALYTICS_ENABLED = (import.meta.env.VITE_ANALYTICS_ENABLED ?? 'false').toLowerCase() === 'true'

export function trackEvent(eventName: string, properties?: Record<string, string | number | boolean>) {
  if (!ANALYTICS_ENABLED) return

  const payload = {
    event: eventName,
    properties: properties ?? {},
    timestamp: new Date().toISOString(),
  }

  if (typeof window !== 'undefined') {
    const existing = window.sessionStorage.getItem('ecomind_analytics_events')
    const events = existing ? JSON.parse(existing) : []
    events.push(payload)
    window.sessionStorage.setItem('ecomind_analytics_events', JSON.stringify(events.slice(-50)))
  }
}
