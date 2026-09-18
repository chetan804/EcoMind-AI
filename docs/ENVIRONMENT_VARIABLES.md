# Environment Variables

## Backend

- `DATABASE_URL`: PostgreSQL connection string.
- `SECRET_KEY`: unique JWT signing secret; production requires at least 32 characters.
- `JWT_ALGORITHM`: JWT algorithm, default `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: positive access-token lifetime.
- `ENVIRONMENT`: `development` or `production`.
- `CORS_ORIGINS`: comma-separated allowed browser origins.
- `APP_VERSION`: application version reported by health endpoints.
- `AI_PROVIDER`, `AI_MODEL`: configured AI provider metadata.
- `ROUTING_PROVIDER`: `fallback` or `osrm`.
- `OSRM_BASE_URL`: OSRM service base URL when routing is enabled.
- `OLLAMA_BASE_URL`: optional local assistant URL.

## Compose

- `POSTGRES_PASSWORD`: required database password.
- `SECRET_KEY`: required backend signing secret.
- `CORS_ORIGINS`: optional browser-origin override.

Never commit `.env` files, credentials, private keys, or provider tokens.
