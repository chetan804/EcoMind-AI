# Map assets (shipped with the app)

Fonts and sprites used by the built-in offline map (`frontend/src/features/maps`). Nothing here is fetched from a third party at run time.

| Path | What | Source | Licence |
|---|---|---|---|
| `fonts/Noto Sans {Regular,Medium,Italic}/` | Glyph PBFs for the Latin ranges only (`0-255`, `256-511`, `8192-8447`) | `protomaps/basemaps-assets` (`fonts/`, generated with maplibre/font-maker from Noto Sans) | SIL Open Font License 1.1 (`fonts/OFL.txt`) |
| `sprites/v4/light*` | POI/shield icons for the `light` basemap flavour | `protomaps/basemaps-assets` (`sprites/v4`), derived from tangrams/icons | MIT |

Other scripts (Devanagari, Telugu, Arabic and so on) are **not** included: place names in those scripts render without labels until the matching ranges are copied from the same repository
(`scripts/maps/fetch_map_assets.py --all-ranges`). The tile file itself (`/map-assets/tiles/region.pmtiles`) is not part of the repository; see `docs/maps/OFFLINE_MAPS.md`.
