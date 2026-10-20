import {
  Bell,
  BookOpen,
  Building2,
  ClipboardList,
  Factory,
  FileText,
  Gift,
  LayoutDashboard,
  LineChart,
  QrCode,
  Route,
  ScanSearch,
  Settings,
  ShieldAlert,
  Store,
  TrendingUp,
  TriangleAlert,
  Truck,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  to: string;
  icon: LucideIcon;
  /** `available` = implemented in this build. `planned` = route exists but shows a "not built yet" page. */
  status: 'available' | 'planned';
  /** The item is shown only to people holding at least one of these permissions (UX only; the server enforces access). */
  anyOf?: string[];
}

/**
 * Primary navigation (order follows the design references).
 * Smart Bins & Telemetry is intentionally NOT an entry: it is excluded by product decision
 * (see docs/architecture/component-boundaries.md). Do not add it.
 */
export const primaryNav: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard, status: 'available' },
  { id: 'analytics', label: 'Analytics', to: '/analytics', icon: LineChart, status: 'available', anyOf: ['analytics:read'] },
  { id: 'classification', label: 'Classification', to: '/classify', icon: ScanSearch, status: 'available', anyOf: ['classification:predict'] },
  { id: 'collections', label: 'Collections', to: '/collection', icon: ClipboardList, status: 'planned', anyOf: ['collection:read'] },
  { id: 'routes', label: 'Routes', to: '/routes', icon: Route, status: 'available', anyOf: ['routes:read'] },
  { id: 'forecasting', label: 'Forecasting', to: '/forecasts', icon: TrendingUp, status: 'available', anyOf: ['forecasting:read'] },
  { id: 'anomalies', label: 'Anomalies', to: '/anomalies', icon: TriangleAlert, status: 'available', anyOf: ['anomalies:read'] },
  { id: 'incidents', label: 'Incidents', to: '/incidents', icon: ShieldAlert, status: 'available', anyOf: ['incidents:create', 'incidents:read_own', 'incidents:triage'] },
  { id: 'alerts', label: 'Alerts', to: '/notifications', icon: Bell, status: 'available', anyOf: ['notifications:read_own'] },
  { id: 'vehicles', label: 'Vehicles', to: '/fleet', icon: Truck, status: 'planned', anyOf: ['fleet:read'] },
  { id: 'facilities', label: 'Facilities', to: '/facilities', icon: Building2, status: 'planned', anyOf: ['facilities:read'] },
  { id: 'marketplace', label: 'Marketplace', to: '/circular-economy', icon: Store, status: 'planned' },
  { id: 'reports', label: 'Reports', to: '/reports', icon: FileText, status: 'planned', anyOf: ['waste_reports:read_own', 'waste_reports:read_all', 'waste_reports:create'] },
  { id: 'guide', label: 'Guide', to: '/sorting-guide', icon: BookOpen, status: 'planned' },
  { id: 'traceability', label: 'Traceability', to: '/passports', icon: QrCode, status: 'planned' },
  { id: 'rewards', label: 'Rewards', to: '/rewards', icon: Gift, status: 'planned' },
];

export const secondaryNav: NavItem[] = [
  { id: 'settings', label: 'Settings', to: '/settings/system-status', icon: Settings, status: 'available' },
];

/** Operations area icon reused by the planned-feature page. */
export const plannedAreaIcon = Factory;

export const allNav: NavItem[] = [...primaryNav, ...secondaryNav];

/** Entries the person may use. Planned (unbuilt) entries stay visible to everyone: they carry the "Soon" label. */
export const visibleNav = (items: NavItem[], can: (permission: string) => boolean): NavItem[] =>
  items.filter((item) => item.status === 'planned' || !item.anyOf || item.anyOf.some(can));

export function findNavItem(pathname: string): NavItem | undefined {
  return allNav.find((item) => pathname === item.to || pathname.startsWith(`${item.to}/`));
}
