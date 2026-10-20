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
  ScanSearch,
  Settings,
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
}

/**
 * Primary navigation (order follows the design references).
 * Smart Bins & Telemetry is intentionally NOT an entry: it is excluded by product decision
 * (see docs/architecture/component-boundaries.md). Do not add it.
 */
export const primaryNav: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard, status: 'available' },
  { id: 'analytics', label: 'Analytics', to: '/analytics', icon: LineChart, status: 'available' },
  { id: 'classification', label: 'Classification', to: '/classify', icon: ScanSearch, status: 'available' },
  { id: 'collections', label: 'Collections', to: '/collection', icon: ClipboardList, status: 'planned' },
  { id: 'forecasting', label: 'Forecasting', to: '/forecasts', icon: TrendingUp, status: 'available' },
  { id: 'anomalies', label: 'Anomalies', to: '/anomalies', icon: TriangleAlert, status: 'available' },
  { id: 'alerts', label: 'Alerts', to: '/notifications', icon: Bell, status: 'available' },
  { id: 'vehicles', label: 'Vehicles', to: '/fleet', icon: Truck, status: 'planned' },
  { id: 'facilities', label: 'Facilities', to: '/facilities', icon: Building2, status: 'planned' },
  { id: 'marketplace', label: 'Marketplace', to: '/circular-economy', icon: Store, status: 'planned' },
  { id: 'reports', label: 'Reports', to: '/reports', icon: FileText, status: 'planned' },
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

export function findNavItem(pathname: string): NavItem | undefined {
  return allNav.find((item) => pathname === item.to || pathname.startsWith(`${item.to}/`));
}
