from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.database import get_db
from app.models.collection import WasteCollection
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionStatusUpdate,
)


router = APIRouter(
    prefix="/collections",
    tags=["Waste Collections"],
)


@router.post(
    "/",
    response_model=CollectionResponse,
)
def create_collection(
    collection_data: CollectionCreate,
    current_user: User = Depends(require_role(4)),
    db: Session = Depends(get_db),
):
    report = (
        db.query(WasteReport)
        .filter(WasteReport.id == collection_data.report_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Waste report not found",
        )

    existing_collection = (
        db.query(WasteCollection)
        .filter(
            WasteCollection.report_id
            == collection_data.report_id
        )
        .first()
    )

    if existing_collection:
        raise HTTPException(
            status_code=400,
            detail="Collection already exists for this report",
        )

    if collection_data.collector_id is not None:
        collector = (
            db.query(User)
            .filter(
                User.id == collection_data.collector_id,
                User.role_id == 6,
            )
            .first()
        )

        if not collector:
            raise HTTPException(
                status_code=400,
                detail="Invalid collector",
            )

    collection = WasteCollection(
        report_id=collection_data.report_id,
        collector_id=collection_data.collector_id,
        scheduled_at=collection_data.scheduled_at,
        status="assigned",
    )

    db.add(collection)

    report.status = "assigned"

    db.commit()
    db.refresh(collection)

    return collection


@router.get(
    "/my-collections",
    response_model=list[CollectionResponse],
)
def get_my_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collections = (
        db.query(WasteCollection)
        .filter(
            WasteCollection.collector_id
            == current_user.id
        )
        .order_by(WasteCollection.created_at.desc())
        .all()
    )

    return collections


@router.get(
    "/admin/all",
    response_model=list[CollectionResponse],
)
def get_all_collections(
    current_user: User = Depends(require_role(4)),
    db: Session = Depends(get_db),
):
    collections = (
        db.query(WasteCollection)
        .order_by(WasteCollection.created_at.desc())
        .all()
    )

    return collections


@router.patch(
    "/{collection_id}/status",
    response_model=CollectionResponse,
)
def update_collection_status(
    collection_id: int,
    status_data: CollectionStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_statuses = {
        "assigned",
        "in_progress",
        "collected",
        "cancelled",
    }

    if status_data.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid collection status",
        )

    collection = (
        db.query(WasteCollection)
        .filter(WasteCollection.id == collection_id)
        .first()
    )

    if not collection:
        raise HTTPException(
            status_code=404,
            detail="Collection not found",
        )

    is_admin = current_user.role_id == 4
    is_assigned_collector = (
        current_user.role_id == 6
        and collection.collector_id == current_user.id
    )

    if not is_admin and not is_assigned_collector:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
        )

    collection.status = status_data.status

    if status_data.status == "collected":
        collection.collected_at = datetime.now(timezone.utc)

        report = (
            db.query(WasteReport)
            .filter(
                WasteReport.id == collection.report_id
            )
            .first()
        )

        if report:
            report.status = "collected"

    db.commit()
    db.refresh(collection)

    return collection