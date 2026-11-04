/**
 * What each account type is for and how a person gets it. This mirrors the server's role catalogue
 * (backend/app/modules/users/rbac.py), which is the authority: the server enforces every permission
 * and refuses self-assigned roles. Nothing here grants access; it only explains it.
 */
export type RoleKey = 'citizen' | 'collector' | 'facility_operator' | 'manager' | 'administrator';

export interface RoleInfo {
  key: RoleKey;
  label: string;
  summary: string;
  access: string[];
  /** `instant`: public registration. `approval`: request, an administrator decides. `protected`: never requested. */
  availability: 'instant' | 'approval' | 'protected';
}

export const ROLE_INFO: RoleInfo[] = [
  {
    key: 'citizen',
    label: 'Citizen',
    summary: 'Residents who report waste and problems and take part in recycling.',
    access: ['Submit and track waste reports', 'Report community incidents', 'Sorting guide and marketplace', 'Rewards and notifications'],
    availability: 'instant',
  },
  {
    key: 'collector',
    label: 'Collector',
    summary: 'Field crews who work the collection tasks they are assigned.',
    access: ['Assigned collection tasks and routes', 'Record collection events and weights', 'Share their vehicle position while on a task'],
    availability: 'approval',
  },
  {
    key: 'facility_operator',
    label: 'Facility operator',
    summary: 'Staff at processing facilities and depots who handle intake and recovery.',
    access: ['Facility and intake records', 'Material recovery records', 'Chain-of-custody passports', 'Classification review queue'],
    availability: 'approval',
  },
  {
    key: 'manager',
    label: 'Manager',
    summary: 'Municipal operations staff who plan and supervise collection.',
    access: ['Operations dashboard and analytics', 'Collections, routes, fleet and facilities', 'Incident triage and report review', 'Forecasts and anomaly alerts'],
    availability: 'approval',
  },
  {
    key: 'administrator',
    label: 'Administrator',
    summary: 'Platform owners who manage people, security and the audit trail.',
    access: ['User and role management', 'Security settings and audit log', 'Model activation and system status'],
    availability: 'protected',
  },
];

export const REQUESTABLE = ROLE_INFO.filter((r) => r.availability === 'approval');

export const AVAILABILITY_LABEL: Record<RoleInfo['availability'], string> = {
  instant: 'Open to everyone',
  approval: 'Administrator approval required',
  protected: 'Not available through sign-up',
};
