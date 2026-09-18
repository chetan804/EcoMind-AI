# EcoMind AI Security Baseline

## Implemented controls

- bcrypt password hashing.
- Expiring JWT access tokens.
- Database-backed active-user and role-name authorization.
- Resource ownership checks on citizen report/classification and collector route/collection operations.
- Pydantic input validation and coordinate bounds.
- Safe generic unexpected-error responses.
- Transaction rollback at the database dependency boundary.
- Request correlation IDs and security response headers.
- Production rejection of placeholder or short JWT secrets.
- Compose secrets supplied through environment variables.

## Required before public production

- Login and registration rate limiting.
- Refresh-token rotation and session revocation.
- Password reset and email verification.
- Organization/tenant isolation.
- Secure object storage and malware scanning for uploads.
- Audit event persistence.
- Dependency and container vulnerability scanning.
- TLS reverse proxy and tested backup restoration.
- API, authorization, IDOR/BOLA, and penetration testing.

The current application must not be described as security-compliant or production-certified until these controls are reviewed in the deployment environment.
