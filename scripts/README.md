# Scripts

Small, readable helper scripts. Scripts must be non-destructive by default (no dropping databases or deleting volumes); anything destructive needs an explicit, clearly named flag and documentation.

| Directory | Contents |
|---|---|
| `setup/` | `init_env.py`: create `.env` files from templates and generate local secrets (`make env`). `init_demo_mail.py`: generate the git-ignored `.env.demo-mail` for the local Mailpit demo inbox (`make demo-mail-up`). |
| `quality/` | `check_structure.py` (canonical structure), `check_env_templates.py` (no secrets in templates). Run by `make check` and CI. |
| `maps/` | `prepare_offline_maps.py`: copy more font ranges (`assets`) and cut the regional tile file (`tiles`, wraps the `pmtiles` CLI) for the offline map. Owner-run, needs network. See `docs/maps/OFFLINE_MAPS.md`. |
| `maps/` (also) | `mbtiles_to_pmtiles.py`: convert a MapTiler / OpenMapTiles MBTiles file to the PMTiles file the app reads (`--output`, `--maxzoom`, `--force`; dependencies hash-pinned in `maps/requirements.lock`). `make_openmaptiles_fixture.py`: tiny synthetic tile file for tests only. See `docs/maps/OFFLINE_MAPS.md`. |
| `perf/` | `load_test.py`: read-only HTTP load test (stdlib only; refuses a non-local target unless `--allow-remote` is given; reports latency percentiles and error rates, optional `--json` output and `--max-p95-ms` / `--max-error-rate` gates). Sandbox results and caveats: `docs/operations/load-testing.md`. |
| `demo/` | `seed_demo.py` (labelled demo data), `verify_smtp_local.py` (checks the local Mailpit mail path end to end). |
| `ml/` | `ksu_route_validation.py` (route optimiser vs a real routing benchmark), `taco_licence.py` (TACO licence audit and owner-run image import), `taco_flickr_verify.py` (owner-run source-licence check). See `docs/ml/dataset-research/TACO_LICENCE_AUDIT.md`. |
| `development/`, `database/`, `security/` | Helper and generator scripts (generated-docs `--check` modes); see each script's docstring. Migrations are run with Alembic directly (`make migrate`). |
