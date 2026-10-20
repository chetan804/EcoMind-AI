# Notifications API

Base path `/api/v1/notifications`. Every endpoint needs `notifications:read_own` and only ever concerns the caller's own notifications.

| Method and path | Purpose |
|---|---|
| `GET /notifications` | Paginated, newest first (`unread_only`, `category`) |
| `GET /notifications/unread-count` | `{unread}` |
| `POST /notifications/{id}/read` | Mark one read (idempotent; the first `read_at` is kept) |
| `POST /notifications/read-all` | `{marked}`: number of notifications changed |

Another user's notification is indistinguishable from a missing one (`404`). Categories: `collection, report, incident, anomaly, reward, system`. Notifications are created by the modules that cause them (assignment, task outcome, rewards, anomalies); this API cannot create them. Email delivery is not implemented.
