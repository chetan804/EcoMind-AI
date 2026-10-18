# Data dictionary

> **Generated** by `scripts/database/generate_data_dictionary.py` from the SQLAlchemy models. Do not edit by hand; run `make data-dictionary`. CI fails if this file is stale.

Conventions are described in [schema-overview.md](schema-overview.md). `PK` primary key, `FK` foreign key, `UQ` unique, `NN` not null. Quantity units are part of the column name (`*_kg`, `*_km`, `*_min`, `*_bytes`, `*_px`) or an explicit `unit` column.

## Module `anomaly_detection`

### `anomaly_alerts`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `metric` | varchar(64) | NN |  |  |
| `unit` | varchar(12) | NN |  |  |
| `severity` | varchar(16) | NN |  |  |
| `status` | varchar(22) | NN | `open` |  |
| `facility_id` | uuid | null |  | FK -> `facilities.id` |
| `material_category_id` | uuid | null |  | FK -> `material_categories.id` |
| `window_start` | timestamptz | NN |  |  |
| `window_end` | timestamptz | NN |  |  |
| `observed_value` | numeric(16, 3) | NN |  |  |
| `expected_value` | numeric(16, 3) | NN |  |  |
| `threshold_value` | numeric(16, 3) | null |  |  |
| `detector_name` | varchar(100) | NN |  |  |
| `detector_version` | varchar(50) | NN |  |  |
| `explanation` | text | NN |  |  |
| `detected_at` | timestamptz | NN |  |  |
| `acknowledged_by_id` | uuid | null |  | FK -> `users.id` |
| `acknowledged_at` | timestamptz | null |  |  |
| `resolved_at` | timestamptz | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_anomaly_alerts_explanation_required`: `length(explanation) > 0`
- `ck_anomaly_alerts_window_ordered`: `window_end > window_start`
- Allowed values: `unit` in (kg, t, m3, l, item); `severity` in (info, warning, critical); `status` in (open, acknowledged, resolved, false_positive)

## Module `audit`

### `audit_logs`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `actor_id` | uuid | null |  | FK -> `users.id` ON DELETE SET NULL |
| `action` | varchar(100) | NN |  |  |
| `entity_type` | varchar(64) | NN |  |  |
| `entity_id` | uuid | null |  |  |
| `occurred_at` | timestamptz | NN | `now()` |  |
| `request_id` | varchar(64) | null |  |  |
| `ip_address` | varchar(45) | null |  |  |
| `changes` | jsonb | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |

## Module `auth`

### `auth_sessions`

One issued refresh token. Rotation creates a new row in the same ``family_id``;     presenting an already-rotated token revokes the whole family (reuse detection).

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | uuid | NN |  | FK -> `users.id` ON DELETE CASCADE |
| `family_id` | uuid | NN | `gen_random_uuid()` |  |
| `token_hash` | varchar(64) | NN |  | UQ |
| `expires_at` | timestamptz | NN |  |  |
| `rotated_at` | timestamptz | null |  |  |
| `revoked_at` | timestamptz | null |  |  |
| `user_agent` | varchar(255) | null |  |  |
| `ip_address` | varchar(45) | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_auth_sessions_expiry_after_creation`: `expires_at > created_at`

## Module `circular_economy`

### `recovery_records`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `facility_id` | uuid | NN |  | FK -> `facilities.id` |
| `material_category_id` | uuid | NN |  | FK -> `material_categories.id` |
| `collection_task_id` | uuid | null |  | FK -> `collection_tasks.id` |
| `evidence_media_asset_id` | uuid | null |  | FK -> `media_assets.id` |
| `recovery_method` | varchar(24) | NN |  |  |
| `input_weight_kg` | numeric(14, 3) | NN |  |  |
| `recovered_weight_kg` | numeric(14, 3) | NN |  |  |
| `processed_at` | timestamptz | NN |  |  |
| `created_by_id` | uuid | NN |  | FK -> `users.id` |
| `verification_status` | varchar(16) | NN | `pending` |  |
| `verified_by_id` | uuid | null |  | FK -> `users.id` |
| `verified_at` | timestamptz | null |  |  |
| `notes` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_recovery_records_input_weight_positive`: `input_weight_kg > 0`
- `ck_recovery_records_recovered_within_input`: `recovered_weight_kg >= 0 AND recovered_weight_kg <= input_weight_kg`
- `ck_recovery_records_verification_timestamp_consistent`: `(verification_status = 'pending') = (verified_at IS NULL)`
- `ck_recovery_records_verifier_consistent`: `(verification_status = 'pending') = (verified_by_id IS NULL)`
- Allowed values: `recovery_method` in (recycled, composted, reused, refurbished, energy_recovered); `verification_status` in (pending, verified, rejected)

## Module `classification`

### `classification_model_versions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `name` | varchar(100) | NN |  |  |
| `version` | varchar(50) | NN |  |  |
| `status` | varchar(17) | NN | `candidate` |  |
| `framework` | varchar(50) | null |  |  |
| `artifact_manifest_sha256` | varchar(64) | null |  |  |
| `evaluation_metrics` | jsonb | null |  |  |
| `trained_at` | timestamptz | null |  |  |
| `activated_at` | timestamptz | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `uq_classification_model_versions_name_version`: unique (name, version)
- Allowed values: `status` in (candidate, active, retired)

### `classification_predictions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `media_asset_id` | uuid | NN |  | FK -> `media_assets.id` ON DELETE CASCADE |
| `model_version_id` | uuid | NN |  | FK -> `classification_model_versions.id` |
| `object_label` | varchar(200) | null |  |  |
| `object_confidence` | numeric(5, 4) | null |  |  |
| `material_category_id` | uuid | NN |  | FK -> `material_categories.id` |
| `material_confidence` | numeric(5, 4) | NN |  |  |
| `review_status` | varchar(18) | NN | `unreviewed` |  |
| `reviewed_material_category_id` | uuid | null |  | FK -> `material_categories.id` |
| `reviewed_by_id` | uuid | null |  | FK -> `users.id` |
| `reviewed_at` | timestamptz | null |  |  |
| `review_notes` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_classification_predictions_correction_has_category`: `(review_status = 'corrected') = (reviewed_material_category_id IS NOT NULL)`
- `ck_classification_predictions_material_confidence_range`: `material_confidence BETWEEN 0 AND 1`
- `ck_classification_predictions_object_confidence_range`: `object_confidence BETWEEN 0 AND 1`
- `ck_classification_predictions_review_timestamp_consistent`: `(review_status = 'unreviewed') = (reviewed_at IS NULL)`
- `uq_classification_predictions_media_asset_id_model_version_id`: unique (media_asset_id, model_version_id)
- Allowed values: `review_status` in (unreviewed, confirmed, corrected, rejected)

## Module `collection`

### `collection_assignments`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `collection_task_id` | uuid | NN |  | FK -> `collection_tasks.id` ON DELETE CASCADE |
| `assignee_id` | uuid | NN |  | FK -> `users.id` |
| `vehicle_id` | uuid | null |  | FK -> `fleet_vehicles.id` |
| `assigned_by_id` | uuid | NN |  | FK -> `users.id` |
| `assigned_at` | timestamptz | NN | `now()` |  |
| `unassigned_at` | timestamptz | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_collection_assignments_unassigned_after_assigned`: `unassigned_at IS NULL OR unassigned_at >= assigned_at`
- `uq_collection_assignments_active_task`: unique index WHERE `unassigned_at IS NULL`

### `collection_events`

Something that happened in the field for a task (arrival, pick-up, delivery...).

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `collection_task_id` | uuid | NN |  | FK -> `collection_tasks.id` ON DELETE CASCADE |
| `event_type` | varchar(29) | NN |  |  |
| `occurred_at` | timestamptz | NN |  |  |
| `recorded_by_id` | uuid | NN |  | FK -> `users.id` |
| `facility_id` | uuid | null |  | FK -> `facilities.id` |
| `collected_weight_kg` | numeric(12, 3) | null |  |  |
| `notes` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `latitude` | numeric(9, 6) | null |  |  |
| `longitude` | numeric(9, 6) | null |  |  |

Constraints:

- `ck_collection_events_geo_point_complete`: `(latitude IS NULL) = (longitude IS NULL)`
- `ck_collection_events_latitude_range`: `latitude BETWEEN -90 AND 90`
- `ck_collection_events_longitude_range`: `longitude BETWEEN -180 AND 180`
- `ck_collection_events_weight_non_negative`: `collected_weight_kg IS NULL OR collected_weight_kg >= 0`
- Allowed values: `event_type` in (arrived, collected, skipped, contaminated, delivered_to_facility)

### `collection_task_status_history`

Append-only log of status transitions.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `collection_task_id` | uuid | NN |  | FK -> `collection_tasks.id` ON DELETE CASCADE |
| `from_status` | varchar(19) | null |  |  |
| `to_status` | varchar(19) | NN |  |  |
| `changed_by_id` | uuid | NN |  | FK -> `users.id` |
| `note` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |

Constraints:

- Allowed values: `from_status` in (pending, assigned, in_progress, completed, failed, cancelled); `to_status` in (pending, assigned, in_progress, completed, failed, cancelled)

### `collection_tasks`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `waste_report_id` | uuid | null |  | FK -> `waste_reports.id` |
| `destination_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `created_by_id` | uuid | NN |  | FK -> `users.id` |
| `title` | varchar(200) | NN |  |  |
| `status` | varchar(19) | NN | `pending` |  |
| `priority` | varchar(14) | NN | `normal` |  |
| `address_text` | varchar(500) | null |  |  |
| `due_at` | timestamptz | null |  |  |
| `notes` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |
| `latitude` | numeric(9, 6) | null |  |  |
| `longitude` | numeric(9, 6) | null |  |  |

Constraints:

- `ck_collection_tasks_geo_point_complete`: `(latitude IS NULL) = (longitude IS NULL)`
- `ck_collection_tasks_latitude_range`: `latitude BETWEEN -90 AND 90`
- `ck_collection_tasks_longitude_range`: `longitude BETWEEN -180 AND 180`
- Allowed values: `status` in (pending, assigned, in_progress, completed, failed, cancelled); `priority` in (low, normal, high, urgent)

## Module `community_incidents`

### `community_incidents`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `reporter_id` | uuid | NN |  | FK -> `users.id` |
| `assigned_to_id` | uuid | null |  | FK -> `users.id` |
| `photo_media_asset_id` | uuid | null |  | FK -> `media_assets.id` |
| `incident_type` | varchar(25) | NN |  |  |
| `status` | varchar(20) | NN | `open` |  |
| `title` | varchar(200) | NN |  |  |
| `description` | text | null |  |  |
| `address_text` | varchar(500) | null |  |  |
| `resolved_at` | timestamptz | null |  |  |
| `resolution_notes` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |
| `latitude` | numeric(9, 6) | null |  |  |
| `longitude` | numeric(9, 6) | null |  |  |

Constraints:

- `ck_community_incidents_geo_point_complete`: `(latitude IS NULL) = (longitude IS NULL)`
- `ck_community_incidents_latitude_range`: `latitude BETWEEN -90 AND 90`
- `ck_community_incidents_longitude_range`: `longitude BETWEEN -180 AND 180`
- `ck_community_incidents_resolution_timestamp_consistent`: `(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)`
- Allowed values: `incident_type` in (illegal_dumping, overflowing_bin, hazardous_waste, missed_collection, open_burning, other); `status` in (open, acknowledged, in_progress, resolved, dismissed)

## Module `facilities`

### `facilities`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `code` | varchar(32) | NN |  | UQ |
| `name` | varchar(200) | NN |  |  |
| `facility_type` | varchar(25) | NN |  |  |
| `status` | varchar(19) | NN | `active` |  |
| `address_line` | varchar(300) | null |  |  |
| `city` | varchar(120) | null |  |  |
| `region` | varchar(120) | null |  |  |
| `country_code` | varchar(2) | null |  |  |
| `daily_capacity_kg` | numeric(14, 3) | null |  |  |
| `contact_email` | varchar(320) | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |
| `latitude` | numeric(9, 6) | null |  |  |
| `longitude` | numeric(9, 6) | null |  |  |

Constraints:

- `ck_facilities_capacity_positive`: `daily_capacity_kg IS NULL OR daily_capacity_kg > 0`
- `ck_facilities_geo_point_complete`: `(latitude IS NULL) = (longitude IS NULL)`
- `ck_facilities_latitude_range`: `latitude BETWEEN -90 AND 90`
- `ck_facilities_longitude_range`: `longitude BETWEEN -180 AND 180`
- Allowed values: `facility_type` in (processing_center, depot, transfer_station, drop_off_point); `status` in (active, inactive, maintenance)

## Module `fleet`

### `fleet_vehicles`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `registration_number` | varchar(32) | NN |  | UQ |
| `vehicle_type` | varchar(23) | NN |  |  |
| `status` | varchar(19) | NN | `available` |  |
| `capacity_kg` | numeric(12, 3) | NN |  |  |
| `home_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_fleet_vehicles_capacity_positive`: `capacity_kg > 0`
- Allowed values: `vehicle_type` in (compactor_truck, tipper_truck, van, cargo_bike, other); `status` in (available, in_service, maintenance, retired)

## Module `forecasting`

### `forecast_results`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `metric` | varchar(64) | NN |  |  |
| `unit` | varchar(12) | NN |  |  |
| `granularity` | varchar(13) | NN |  |  |
| `facility_id` | uuid | null |  | FK -> `facilities.id` |
| `material_category_id` | uuid | null |  | FK -> `material_categories.id` |
| `period_start` | timestamptz | NN |  |  |
| `period_end` | timestamptz | NN |  |  |
| `predicted_value` | numeric(16, 3) | NN |  |  |
| `lower_bound` | numeric(16, 3) | null |  |  |
| `upper_bound` | numeric(16, 3) | null |  |  |
| `model_name` | varchar(100) | NN |  |  |
| `model_version` | varchar(50) | NN |  |  |
| `generated_at` | timestamptz | NN |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_forecast_results_interval_ordered`: `lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound`
- `ck_forecast_results_period_ordered`: `period_end > period_start`
- Allowed values: `unit` in (kg, t, m3, l, item); `granularity` in (day, week, month)

## Module `material_passports`

### `custody_events`

Append-only chain-of-custody entry; ``sequence`` orders events within a passport.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `material_passport_id` | uuid | NN |  | FK -> `material_passports.id` ON DELETE CASCADE |
| `sequence` | integer | NN |  |  |
| `event_type` | varchar(19) | NN |  |  |
| `occurred_at` | timestamptz | NN |  |  |
| `actor_id` | uuid | NN |  | FK -> `users.id` |
| `from_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `to_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `notes` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_custody_events_sequence_positive`: `sequence >= 1`
- `uq_custody_events_material_passport_id_sequence`: unique (material_passport_id, sequence)
- Allowed values: `event_type` in (created, collected, transferred, received, processed, verified)

### `material_passports`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `passport_code` | varchar(64) | NN |  | UQ |
| `material_category_id` | uuid | NN |  | FK -> `material_categories.id` |
| `status` | varchar(21) | NN | `active` |  |
| `description` | text | null |  |  |
| `weight_kg` | numeric(14, 3) | NN |  |  |
| `origin_collection_task_id` | uuid | null |  | FK -> `collection_tasks.id` |
| `recovery_record_id` | uuid | null |  | FK -> `recovery_records.id` |
| `current_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `created_by_id` | uuid | NN |  | FK -> `users.id` |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_material_passports_weight_positive`: `weight_kg > 0`
- Allowed values: `status` in (active, in_processing, recovered, retired)

## Module `notifications`

### `notifications`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `recipient_id` | uuid | NN |  | FK -> `users.id` ON DELETE CASCADE |
| `category` | varchar(18) | NN |  |  |
| `title` | varchar(200) | NN |  |  |
| `body` | text | null |  |  |
| `entity_type` | varchar(64) | null |  |  |
| `entity_id` | uuid | null |  |  |
| `read_at` | timestamptz | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |

Constraints:

- Allowed values: `category` in (collection, report, incident, anomaly, reward, system)

## Module `rewards`

### `reward_ledger_entries`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | uuid | NN |  | FK -> `users.id` |
| `entry_type` | varchar(18) | NN |  |  |
| `points` | integer | NN |  |  |
| `impact_weight_kg` | numeric(14, 3) | null |  |  |
| `source_type` | varchar(26) | NN |  |  |
| `source_id` | uuid | null |  |  |
| `reverses_entry_id` | uuid | null |  | FK -> `reward_ledger_entries.id` |
| `created_by_id` | uuid | null |  | FK -> `users.id` |
| `description` | varchar(500) | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_reward_ledger_entries_impact_non_negative`: `impact_weight_kg IS NULL OR impact_weight_kg >= 0`
- `ck_reward_ledger_entries_points_non_zero`: `points <> 0`
- `ck_reward_ledger_entries_reversal_references_entry`: `(entry_type = 'reversal') = (reverses_entry_id IS NOT NULL)`
- `uq_reward_ledger_entries_idempotency`: unique index WHERE `source_id IS NOT NULL AND entry_type = 'earned'`
- Allowed values: `entry_type` in (earned, redeemed, adjustment, reversal); `source_type` in (waste_report, collection_task, recovery_record, community_incident, manual)

## Module `route_planning`

### `route_plans`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `name` | varchar(200) | NN |  |  |
| `planned_date` | date | NN |  |  |
| `status` | varchar(19) | NN | `draft` |  |
| `vehicle_id` | uuid | null |  | FK -> `fleet_vehicles.id` |
| `driver_id` | uuid | null |  | FK -> `users.id` |
| `start_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `end_facility_id` | uuid | null |  | FK -> `facilities.id` |
| `created_by_id` | uuid | NN |  | FK -> `users.id` |
| `total_distance_km` | numeric(10, 3) | null |  |  |
| `estimated_duration_min` | integer | null |  |  |
| `optimizer` | varchar(100) | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_route_plans_distance_non_negative`: `total_distance_km IS NULL OR total_distance_km >= 0`
- `ck_route_plans_duration_non_negative`: `estimated_duration_min IS NULL OR estimated_duration_min >= 0`
- Allowed values: `status` in (draft, published, in_progress, completed, cancelled)

### `route_stops`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `route_plan_id` | uuid | NN |  | FK -> `route_plans.id` ON DELETE CASCADE |
| `sequence` | integer | NN |  |  |
| `collection_task_id` | uuid | null |  | FK -> `collection_tasks.id` |
| `facility_id` | uuid | null |  | FK -> `facilities.id` |
| `planned_arrival_at` | timestamptz | null |  |  |
| `actual_arrival_at` | timestamptz | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_route_stops_exactly_one_target`: `num_nonnulls(collection_task_id, facility_id) = 1`
- `ck_route_stops_sequence_positive`: `sequence >= 1`
- `uq_route_stops_route_plan_id_sequence`: unique (route_plan_id, sequence)

## Module `sorting_guide`

### `material_categories`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `code` | varchar(64) | NN |  | UQ |
| `name` | varchar(120) | NN |  |  |
| `description` | text | null |  |  |
| `is_active` | boolean | NN | `true` |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

### `sorting_guidance`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `material_category_id` | uuid | NN |  | FK -> `material_categories.id` ON DELETE CASCADE |
| `disposal_method` | varchar(26) | NN |  |  |
| `title` | varchar(200) | NN |  |  |
| `instructions` | text | NN |  |  |
| `preparation_notes` | text | null |  |  |
| `source_reference` | varchar(500) | null |  |  |
| `is_active` | boolean | NN | `true` |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- Allowed values: `disposal_method` in (recycle, compost, reuse, landfill, hazardous_drop_off, e_waste_drop_off, special_collection)

## Module `users`

### `permissions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `code` | varchar(100) | NN |  | UQ |
| `description` | text | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

### `role_permissions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `role_id` | uuid | NN |  | PK; FK -> `roles.id` ON DELETE CASCADE |
| `permission_id` | uuid | NN |  | PK; FK -> `permissions.id` ON DELETE CASCADE |

### `roles`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `name` | varchar(64) | NN |  | UQ |
| `description` | text | null |  |  |
| `is_system` | boolean | NN | `false` |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

### `user_roles`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `user_id` | uuid | NN |  | PK; FK -> `users.id` ON DELETE CASCADE |
| `role_id` | uuid | NN |  | PK; FK -> `roles.id` ON DELETE CASCADE |
| `assigned_at` | timestamptz | NN | `now()` |  |

### `users`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `email` | varchar(320) | NN |  |  |
| `password_hash` | varchar(255) | NN |  |  |
| `full_name` | varchar(200) | NN |  |  |
| `is_active` | boolean | NN | `true` |  |
| `last_login_at` | timestamptz | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `uq_users_email_lower`: unique index

## Module `waste_reports`

### `media_assets`

Metadata for a stored file. The bytes live in the configured file-storage backend.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `uploaded_by_id` | uuid | NN |  | FK -> `users.id` |
| `waste_report_id` | uuid | null |  | FK -> `waste_reports.id` ON DELETE SET NULL |
| `storage_backend` | varchar(32) | NN |  |  |
| `storage_key` | varchar(500) | NN |  | UQ |
| `original_filename` | varchar(255) | null |  |  |
| `content_type` | varchar(100) | NN |  |  |
| `size_bytes` | bigint | NN |  |  |
| `sha256` | varchar(64) | NN |  |  |
| `width_px` | integer | null |  |  |
| `height_px` | integer | null |  |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |

Constraints:

- `ck_media_assets_sha256_hex_length`: `length(sha256) = 64`
- `ck_media_assets_size_positive`: `size_bytes > 0`

### `waste_reports`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `reporter_id` | uuid | NN |  | FK -> `users.id` |
| `status` | varchar(20) | NN | `submitted` |  |
| `title` | varchar(200) | NN |  |  |
| `description` | text | null |  |  |
| `address_text` | varchar(500) | null |  |  |
| `estimated_weight_kg` | numeric(12, 3) | null |  |  |
| `reported_at` | timestamptz | NN | `now()` |  |
| `id` | uuid | NN | `gen_random_uuid()` | PK |
| `created_at` | timestamptz | NN | `now()` |  |
| `updated_at` | timestamptz | NN | `now()` |  |
| `latitude` | numeric(9, 6) | null |  |  |
| `longitude` | numeric(9, 6) | null |  |  |

Constraints:

- `ck_waste_reports_geo_point_complete`: `(latitude IS NULL) = (longitude IS NULL)`
- `ck_waste_reports_latitude_range`: `latitude BETWEEN -90 AND 90`
- `ck_waste_reports_longitude_range`: `longitude BETWEEN -180 AND 180`
- `ck_waste_reports_weight_non_negative`: `estimated_weight_kg IS NULL OR estimated_weight_kg >= 0`
- Allowed values: `status` in (submitted, under_review, verified, rejected, closed)
