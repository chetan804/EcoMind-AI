# Integration: File storage

Abstraction over where uploaded media bytes live. `FILE_STORAGE_BACKEND=local` writes to `FILE_STORAGE_LOCAL_PATH` (needs a persistent volume). Another backend (for example S3-compatible object storage) is added here, behind the same interface, when deployment requires it. Used by `waste_reports`.

**Status:** implemented (`local` backend) and tested; see `local.py` for the safety rules (key allow-list, root confinement, atomic writes, 0600 files).

Rules: integrations are called by module services, never by routers directly; they hold no business rules and no database tables of their own unless stated above.
