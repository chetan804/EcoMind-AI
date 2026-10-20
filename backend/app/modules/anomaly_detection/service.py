"""Anomaly detection use cases. Reading needs ``anomalies:read``; scanning and handling alerts
need ``anomalies:manage``.

Wording matters: the detector finds *suspected* anomalies in numbers. It cannot know whether the
cause is a real incident, a data-entry mistake or a holiday, and every alert says so.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError
from app.modules.anomaly_detection import repository
from app.modules.anomaly_detection.constants import AlertStatus, AnomalySeverity
from app.modules.anomaly_detection.models import AnomalyAlert
from app.modules.anomaly_detection.schemas import AlertOut, ScanOut, ScanRequest
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.forecasting import engine, series
from app.modules.forecasting.service import InsufficientHistoryError

DETECTOR_VERSION = engine.ENGINE_VERSION
WARN_Z, CRIT_Z = 3.5, 5.0
MIN_HISTORY = 12
_KILO = decimal.Decimal("0.001")
CAVEAT = (
    "Suspected anomalies only: unusual compared with this series' own history. The cause "
    "(real incident, data-entry error, holiday, closure) is not known to the system."
)

ALLOWED: dict[AlertStatus, frozenset[AlertStatus]] = {
    AlertStatus.OPEN: frozenset(
        {AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE}
    ),
    AlertStatus.ACKNOWLEDGED: frozenset({AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE}),
    AlertStatus.RESOLVED: frozenset(),
    AlertStatus.FALSE_POSITIVE: frozenset(),
}


class InvalidAlertTransitionError(AppError):
    status_code = 409
    code = "invalid_alert_transition"


def _dec(value: float) -> decimal.Decimal:
    return decimal.Decimal(repr(float(value))).quantize(_KILO, rounding=decimal.ROUND_HALF_UP)


def _out(alert: AnomalyAlert) -> AlertOut:
    out = AlertOut.model_validate(alert, from_attributes=True)
    out.data_kind = "public_reference" if series.is_reference(alert.metric) else "platform"
    return out


def _detector_name(season: int) -> str:
    return (
        "robust-z: median of the same week in the previous years"
        if season > 1
        else "robust-z: median of the previous three weeks"
    )


def _explain(
    observed: float, expected: float, score: float, season: int, kind: str, warn_z: float
) -> str:
    direction = "higher" if observed > expected else "lower"
    basis = "the same week in previous years" if season > 1 else "the previous three weeks"
    text = (
        f"Weekly total {direction} than expected: {observed:,.0f} kg observed versus about "
        f"{expected:,.0f} kg expected from {basis}. Robust deviation score {score:+.1f} "
        f"(alert from ±{warn_z}). Suspected anomaly, not a confirmed incident."
    )
    if kind == "public_reference":
        text += " Public reference data, not produced by this platform."
    return text


def scan(
    db: Session, principal: Principal, payload: ScanRequest, *, context: RequestContext
) -> ScanOut:
    data = series.load_series(db, payload.series)
    n = len(data.values)
    alg: Any = engine.algorithms()
    season = int(alg.anomaly_season(n))
    warmup = max(2 * season, MIN_HISTORY)
    if n <= warmup:
        raise InsufficientHistoryError(
            f"Detection needs more than {warmup} complete weeks of history; this series has {n}.",
            details=[{"available_weeks": n, "required_weeks": warmup + 1}],
        )
    y = np.asarray(data.values, dtype=np.float64)
    found = alg.detect_anomalies(y, season=season, warn_z=WARN_Z, crit_z=CRIT_Z)
    first_considered = max(0, n - payload.lookback_weeks)
    detector = _detector_name(season)
    kind = data.info.data_kind
    created: list[AnomalyAlert] = []
    existing = 0
    flagged = 0
    for point in found:
        # Interpolated weeks are not observations: never alert on a value we filled in.
        if point.index < first_considered or data.interpolated[point.index]:
            continue
        flagged += 1
        start = dt.datetime.combine(data.periods[point.index], dt.time(), dt.UTC)
        if (
            repository.find_existing(
                db, metric=data.info.ref, window_start=start, detector_name=detector
            )
            is not None
        ):
            existing += 1
            continue
        alert = repository.add(
            db,
            metric=data.info.ref,
            unit=data.info.unit,
            severity=AnomalySeverity(point.severity),
            status=AlertStatus.OPEN,
            window_start=start,
            window_end=start + dt.timedelta(days=7),
            observed_value=_dec(point.observed),
            expected_value=_dec(point.expected),
            threshold_value=_dec(point.tolerance),
            detector_name=detector,
            detector_version=DETECTOR_VERSION,
            explanation=_explain(point.observed, point.expected, point.score, season, kind, WARN_Z),
            detected_at=dt.datetime.now(dt.UTC),
        )
        created.append(alert)
    audit.record(
        db,
        action="anomaly.scan",
        entity_type="anomaly_series",
        actor_id=principal.user_id,
        context=context,
        changes={
            "series": data.info.ref,
            "flagged": flagged,
            "created": len(created),
            "already_recorded": existing,
        },
    )
    db.commit()
    return ScanOut(
        series=data.info.ref,
        data_kind=kind,
        detector=detector,
        weeks_scanned=n,
        weeks_considered=n - first_considered,
        flagged=flagged,
        created=len(created),
        already_recorded=existing,
        alerts=[_out(a) for a in created],
        caveat=CAVEAT,
    )


def list_alerts(
    db: Session,
    params: PageParams,
    *,
    status: AlertStatus | None,
    severity: AnomalySeverity | None,
    metric: str | None,
    data_kind: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[AlertOut]:
    rows, total = repository.list_page(
        db,
        params,
        status=status,
        severity=severity,
        metric=metric,
        data_kind=data_kind,
        sort_by=sort_by,
        order=order,
    )
    return Page.build([_out(r) for r in rows], total, params)


def get_alert(db: Session, alert_id: uuid.UUID) -> AlertOut:
    alert = repository.get(db, alert_id)
    if alert is None:
        raise NotFoundError("Alert not found")
    return _out(alert)


def transition(
    db: Session,
    principal: Principal,
    alert_id: uuid.UUID,
    target: AlertStatus,
    note: str | None,
    *,
    context: RequestContext,
) -> AlertOut:
    alert = repository.get(db, alert_id, for_update=True)
    if alert is None:
        raise NotFoundError("Alert not found")
    if target not in ALLOWED[alert.status]:
        db.rollback()
        raise InvalidAlertTransitionError(
            f"A {alert.status.value} alert cannot become {target.value}"
        )
    before = alert.status
    now = dt.datetime.now(dt.UTC)
    alert.status = target
    if target is AlertStatus.ACKNOWLEDGED:
        alert.acknowledged_by_id, alert.acknowledged_at = principal.user_id, now
    elif target is AlertStatus.RESOLVED:
        alert.resolved_at = now
        if alert.acknowledged_at is None:
            alert.acknowledged_by_id, alert.acknowledged_at = principal.user_id, now
    else:  # false positive: someone reviewed it
        alert.resolved_at = now
        if alert.acknowledged_at is None:
            alert.acknowledged_by_id, alert.acknowledged_at = principal.user_id, now
    audit.record(
        db,
        action=f"anomaly_alert.{target.value}",
        entity_type="anomaly_alert",
        entity_id=alert.id,
        actor_id=principal.user_id,
        context=context,
        changes={"from": before.value, "to": target.value, "note": note},
    )
    db.commit()
    db.refresh(alert)
    return _out(alert)
