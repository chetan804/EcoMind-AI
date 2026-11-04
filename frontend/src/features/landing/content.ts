/**
 * Everything the landing page says, in one place so it can be checked against the product.
 * Rules for this file: no invented partners, certifications, customers, accuracy or impact figures;
 * every statement about behaviour matches the code or a document in the repository; screenshots
 * are real captures of the running application on labelled demonstration data.
 */

export const SECTION_LINKS = [
  { href: '#product', label: 'Product' },
  { href: '#capabilities', label: 'Platform' },
  { href: '#impact', label: 'Impact' },
  { href: '#roles', label: 'Roles' },
  { href: '#security', label: 'Security' },
] as const;

/** Facts about the product today. They are counts of things that exist, not performance claims. */
export const PROJECT_FACTS = [
  { value: '5', label: 'User roles with separate permissions' },
  { value: '10', label: 'Material categories in the sorting guide' },
  { value: '3', label: 'ML capabilities built: classifier, forecasts, anomaly flags' },
  { value: '0', label: 'Classifiers approved for use' },
] as const;

export interface Shot {
  src: string;
  alt: string;
  caption: string;
}

const demoData = 'Demonstration data';

export const SHOTS = {
  dashboard: { src: '/landing/dashboard.webp', alt: 'Command center: collected weight, open tasks, recovery rate, suspected anomalies, a weekly trend and a list of items needing attention', caption: `Command center. ${demoData}.` },
  classify: { src: '/landing/classify.webp', alt: 'AI waste classification screen showing that no classification model is active', caption: 'Classification screen with no approved model: it says so instead of guessing.' },
  forecasts: { src: '/landing/forecasts.webp', alt: 'Collection volume forecast chart with observed history and a dashed forecast with interval bounds', caption: `Observed history and a separate forecast with its interval. ${demoData}.` },
  anomalies: { src: '/landing/anomalies.webp', alt: 'Anomaly list with one suspected anomaly, its explanation and review actions', caption: `A suspected anomaly with the reason it was flagged. ${demoData}.` },
  routes: { src: '/landing/routes-detail.webp', alt: 'Route plan with stops joined by straight dashed lines and a notice that no road route is configured', caption: `A route plan that states its method. ${demoData}.` },
  incidents: { src: '/landing/incidents.webp', alt: 'Community incident triage with counts by status and type and a list of reported incidents', caption: `Community incident triage. ${demoData}.` },
  marketplace: { src: '/landing/marketplace.webp', alt: 'Circular surplus marketplace with three published listings', caption: `Surplus-material listings. ${demoData}.` },
  passport: { src: '/landing/passport-detail.webp', alt: 'Material passport with a four-step chain of custody and an integrity check button', caption: `A passport and its chain of custody. ${demoData}.` },
  recovery: { src: '/landing/recovery.webp', alt: 'Material recovery records with verified and pending status and a recovery rate', caption: `Recovery records, counted only once verified. ${demoData}.` },
  rewards: { src: '/landing/rewards.webp', alt: 'Rewards and impact ledger with a points balance and two ledger entries', caption: `An append-only points ledger. ${demoData}.` },
  collection: { src: '/landing/collection.webp', alt: 'Collection tasks list with status and priority', caption: `Collection tasks. ${demoData}.` },
} as const satisfies Record<string, Shot>;

export interface DemoStep {
  id: string;
  label: string;
  title: string;
  body: string;
  real: string;
  limit: string;
  shot: Shot;
}

/** The walkthrough opened by "Watch demo": screenshots of the real screens, not a video. */
export const DEMO_STEPS: DemoStep[] = [
  {
    id: 'classify',
    label: 'Classify',
    title: '1. Classify an item',
    body: 'A resident or collector chooses a photo. The classifier returns a material category with a confidence, and sends uncertain results to a human review queue.',
    real: 'The screen, upload checks and review queue are built and tested.',
    limit: 'No classifier is approved for use yet. Until one passes the approval checks the screen says "No classification model is active" and does not return a guess.',
    shot: SHOTS.classify,
  },
  {
    id: 'forecast',
    label: 'Forecast',
    title: '2. Forecast collection volume',
    body: 'Weekly volumes are forecast four weeks ahead. History and forecast are drawn separately, with an interval, and the model is shown next to a naive baseline it is tested against.',
    real: 'Forecasts are computed from the series on the server when you press Run forecast. It needs 26 complete weeks of history.',
    limit: 'The chart shows demonstration data. The forecast beat the naive baseline on two of the four series tested; it is not a promise of accuracy on your data.',
    shot: SHOTS.forecasts,
  },
  {
    id: 'anomaly',
    label: 'Anomalies',
    title: '3. Review suspected anomalies',
    body: 'A robust statistical check compares each week with its own history and flags unusual weeks, with a plain-language reason. A manager acknowledges, resolves or marks a flag as a false positive.',
    real: 'Flags are produced by the detector and every lifecycle change is recorded.',
    limit: 'A flag is a statistical outlier, not a confirmed incident. The system cannot know the cause.',
    shot: SHOTS.anomalies,
  },
  {
    id: 'routes',
    label: 'Routes',
    title: '4. Plan a route',
    body: 'A manager orders stops for a vehicle. The plan lists its method and distance, and shows the stops on a map.',
    real: 'Stop order comes from the platform optimiser, measured against an exact search on small test sets (1.096 times the optimum on the benchmark).',
    limit: 'Distances are straight-line. There is no live traffic and no travel-time estimate, and the screen says so when no road routing provider is configured.',
    shot: SHOTS.routes,
  },
  {
    id: 'recovery',
    label: 'Recovery',
    title: '5. Record and verify recovery',
    body: 'Facility staff record what was recovered from a batch. A second person verifies it, and only verified records count towards the recovery rate.',
    real: 'The recovery rate is a mass ratio computed from verified records.',
    limit: 'It is not a landfill-diversion, carbon or cost claim. None of those is computed because none is sourced.',
    shot: SHOTS.recovery,
  },
];

export interface Capability {
  title: string;
  body: string;
}

export const PROBLEMS: Capability[] = [
  { title: 'Mixed material loses its value', body: 'Recyclable material that is collected mixed or contaminated is hard to recover, and nobody sees where it went wrong.' },
  { title: 'Plans run on habit', body: 'Collection rounds are often set by routine rather than by what was actually collected last week.' },
  { title: 'Problems surface late', body: 'Overflowing bins, dumping and missed collections reach the people who can act only after residents complain.' },
  { title: 'Recovery is hard to prove', body: 'Without a record of who held a batch and what came out of it, reuse and recycling claims cannot be checked.' },
];

export const CAPABILITIES: Capability[] = [
  { title: 'Identify waste with computer vision', body: 'Photo classification with confidence and a human review queue. Ships without an approved model.' },
  { title: 'Forecast collection volume', body: 'Weekly forecasts with intervals, tested against a baseline.' },
  { title: 'Flag unusual weeks', body: 'Statistical outliers with a reason, triaged by a person.' },
  { title: 'Order collection routes', body: 'Stop ordering from straight-line distances, labelled as such.' },
  { title: 'Trace material', body: 'Passports with an append-only chain of custody.' },
  { title: 'Enable reuse', body: 'A matching board for surplus material, with no payment or delivery.' },
];

export const WORKFLOW = [
  { title: 'Report', body: 'A resident photographs and reports waste or an incident.' },
  { title: 'Classify', body: 'The item is classified, or sent to a person when the system is unsure.' },
  { title: 'Plan', body: 'A manager turns reports into collection tasks and orders the route.' },
  { title: 'Collect', body: 'A collector works the task and records the weight collected.' },
  { title: 'Recover', body: 'A facility records what was recovered and a second person verifies it.' },
  { title: 'Trace and reward', body: 'The batch keeps its chain of custody and the resident earns points from verified weight.' },
] as const;

export interface RoleCard {
  name: string;
  summary: string;
  how: string;
}

export const ROLES: RoleCard[] = [
  { name: 'Citizen', summary: 'Reports waste and incidents, uses the sorting guide and assistant, earns points.', how: 'Open sign-up. Everyone starts here.' },
  { name: 'Collector', summary: 'Works assigned collection tasks and records weights in the field.', how: 'Request it after sign-up. An administrator approves.' },
  { name: 'Facility operator', summary: 'Records intake and recovery, and manages passports and listings.', how: 'Request it after sign-up. An administrator approves.' },
  { name: 'Manager', summary: 'Plans tasks, routes and fleet, and triages anomalies and incidents.', how: 'Request it after sign-up. An administrator approves.' },
  { name: 'Administrator', summary: 'Manages users, decides role requests, reads the audit log.', how: 'Never self-service. Created through a protected administrator process.' },
];

export const SECURITY_POINTS: Capability[] = [
  { title: 'Roles are enforced on the server', body: 'Every API route checks a named permission. The interface hides what you cannot use, but the server is what refuses.' },
  { title: 'Public sign-up is citizen only', body: 'Operational roles come from a request that an administrator approves, and the decision is audited. Administrator is never offered.' },
  { title: 'Sessions and multi-factor sign-in', body: 'Short-lived access tokens held in memory, an HttpOnly refresh cookie, and multi-factor sign-in with authenticator codes.' },
  { title: 'Append-only records', body: 'The audit log, custody events, collection status history and points ledger cannot be edited after the fact.' },
];

export const TRANSPARENCY_POINTS = [
  'EcoMind AI is under active development and is not deployed in production.',
  'The screenshots on this page are real captures of the running application on demonstration data. No customers, partners or certifications are claimed.',
  'The waste-image classifier is a research candidate that has not passed its approval checks, so it is switched off.',
  'No carbon, cost or landfill-diversion figure is shown because none is sourced.',
] as const;
