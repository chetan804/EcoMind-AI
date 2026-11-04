/** Public interface of the access-requests feature. */
export { AccessPage } from './pages/AccessPage';
export { ReviewQueue } from './components/ReviewQueue';
export { RoleGuide } from './components/RoleGuide';
export { RoleRequestForm } from './components/RoleRequestForm';
export { ROLE_INFO, REQUESTABLE, AVAILABILITY_LABEL, type RoleKey, type RoleInfo } from './roles';
export { createRoleRequest } from './api/access-requests-api';
