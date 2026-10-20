# Scripts

Small, readable helper scripts. Scripts must be non-destructive by default (no dropping databases or deleting volumes); anything destructive needs an explicit, clearly named flag and documentation.

| Directory | Contents |
|---|---|
| `setup/` | `init_env.py`: create `.env` files from templates and generate local secrets (`make env`). |
| `quality/` | `check_structure.py` (canonical structure), `check_env_templates.py` (no secrets in templates). Run by `make check` and CI. |
| `maps/` | `prepare_offline_maps.py`: copy more font ranges (`assets`) and cut the regional tile file (`tiles`, wraps the `pmtiles` CLI) for the offline map. Owner-run, needs network. See `docs/maps/OFFLINE_MAPS.md`. |
| `ml/` | `ksu_route_validation.py` (route optimiser vs a real routing benchmark), `taco_licence.py` (TACO licence audit and owner-run image import), `taco_flickr_verify.py` (owner-run source-licence check). See `docs/ml/dataset-research/TACO_LICENCE_AUDIT.md`. |
| `development/`, `database/`, `security/` | Helper and generator scripts (generated-docs `--check` modes); see each script's docstring. Migrations are run with Alembic directly (`make migrate`). |
