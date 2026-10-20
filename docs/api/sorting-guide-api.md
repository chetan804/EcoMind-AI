# Sorting guide API

Base path `/api/v1/sorting-guide`. Bearer authentication; standard error envelope; pagination via `page`/`page_size`.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /categories` | `sorting_guide:read` | Material categories with the number of **active** guidance entries (`q`, `include_inactive`) |
| `POST /categories` | `sorting_guide:manage` | Add a category (`409` if the code exists) |
| `PATCH /categories/{id}` | `sorting_guide:manage` | Rename, describe, activate/deactivate |
| `GET /guidance` | `sorting_guide:read` | Guidance entries (`category_id`, `disposal_method`, `q`, `include_inactive`, `sort_by`, `order`) |
| `POST /guidance` | `sorting_guide:manage` | Add guidance |
| `GET /guidance/{id}` | `sorting_guide:read` | One entry |
| `PATCH /guidance/{id}` | `sorting_guide:manage` | Edit or deactivate |

Every role can read; managers and administrators can edit (migration 0002).

## Content policy

* **Categories** are seeded by migrations `0004` (the six classes the active model predicts: `cardboard, glass, metal, paper, plastic, trash`) and `0006` (`organic, textile, e_waste, medical`). Only names and one-line descriptions are seeded.
* **No sorting rules are shipped.** Disposal rules differ by municipality, so the platform does not invent them. Administrators add guidance and should record `source_reference`; every entry reports `has_source`, and an entry without a source must be shown as unverified.
* Inactive entries (and entries of inactive categories) are invisible to readers: `include_inactive` is ignored for users without `sorting_guide:manage`, and a direct `GET` of hidden content is `404`.
* Disposal methods: `recycle, compost, reuse, landfill, hazardous_drop_off, e_waste_drop_off, special_collection`.

## Audit events

`material_category.created|updated`, `sorting_guidance.created|updated`.
