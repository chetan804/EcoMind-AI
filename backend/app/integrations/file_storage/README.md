# Integration: File storage

Abstraction over where uploaded media bytes live. `FILE_STORAGE_BACKEND=local` writes to `FILE_STORAGE_LOCAL_PATH` (needs a persistent volume). Another backend (for example S3-compatible object storage) is added here, behind the same interface, when deployment requires it. Used by `waste_reports`.

**Status:** boundary defined only; nothing implemented.

Rules: integrations are called by module services, never by routers directly; they hold no business rules and no database tables of their own unless stated above.
