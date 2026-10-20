"""Anomaly-detection endpoints, mounted at ``/api/v1/anomalies``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.anomaly_detection import service
from app.modules.anomaly_detection.constants import AlertStatus, AnomalySeverity
from app.modules.anomaly_detection.schemas import (
    AlertOut,
    DataKind,
    ScanOut,
    ScanRequest,
    SortField,
    TransitionRequest,
)
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("anomalies:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("anomalies:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.get("", response_model=Page[AlertOut])
def list_alerts(
    db: DbSession,
    _: CanRead,
    params: Pagination,
    status_filter: Annotated[AlertStatus | None, Query(alias="status")] = None,
    severity: AnomalySeverity | None = None,
    series: Annotated[str | None, Query(max_length=80)] = None,
    data_kind: Annotated[
        DataKind | None, Query(description="Defaults to platform data only")
    ] = "platform",
    sort_by: SortField = "detected_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[AlertOut]:
    return service.list_alerts(
        db,
        params,
        status=status_filter,
        severity=severity,
        metric=series,
        data_kind=data_kind,
        sort_by=sort_by,
        order=order,
    )


@router.post("/scan", response_model=ScanOut)
def scan(payload: ScanRequest, request: Request, db: DbSession, principal: CanManage) -> ScanOut:
    """Run the detector over a series and record new suspected anomalies (idempotent)."""
    return service.scan(db, principal, payload, context=_ctx(request))


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: uuid.UUID, db: DbSession, _: CanRead) -> AlertOut:
    return service.get_alert(db, alert_id)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(
    alert_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> AlertOut:
    return service.transition(
        db, principal, alert_id, AlertStatus.ACKNOWLEDGED, payload.note, context=_ctx(request)
    )


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(
    alert_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> AlertOut:
    return service.transition(
        db, principal, alert_id, AlertStatus.RESOLVED, payload.note, context=_ctx(request)
    )


@router.post("/{alert_id}/false-positive", response_model=AlertOut)
def mark_false_positive(
    alert_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> AlertOut:
    """The alert was reviewed and the value is explained or wrong: not an incident."""
    return service.transition(
        db, principal, alert_id, AlertStatus.FALSE_POSITIVE, payload.note, context=_ctx(request)
    )
