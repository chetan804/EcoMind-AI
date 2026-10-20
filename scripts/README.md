# Scripts

Small, readable helper scripts. Scripts must be non-destructive by default (no dropping databases or deleting volumes); anything destructive needs an explicit, clearly named flag and documentation.

| Directory | Contents |
|---|---|
| `setup/` | `init_env.py`: create `.env` files from templates and generate local secrets (`make env`). |
| `quality/` | `check_structure.py` (canonical structure), `check_env_templates.py` (no secrets in templates). Run by `make check` and CI. |
| `development/`, `database/`, `ml/` | Reserved; empty until a script is justified. Migrations are run with Alembic directly (`make migrate`). |
