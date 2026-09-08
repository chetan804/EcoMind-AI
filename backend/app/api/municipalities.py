from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import RoleID
from app.core.security import require_role
from app.db.database import get_db
from app.models.municipality import Municipality, MunicipalSyncLog, ServiceArea
from app.schemas.municipality import (
    MunicipalityCreate,
    MunicipalityResponse,
    ServiceAreaCreate,
    ServiceAreaResponse,
)
from app.services.municipality_service import build_municipality_summary

router = APIRouter(prefix="/municipalities", tags=["Municipalities"])


@router.get("/", response_model=list[MunicipalityResponse])
def list_municipalities(
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return db.query(Municipality).order_by(Municipality.name.asc()).all()


@router.post("/", response_model=MunicipalityResponse, status_code=status.HTTP_201_CREATED)
def create_municipality(
    municipality_data: MunicipalityCreate,
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    existing = db.query(Municipality).filter(Municipality.code == municipality_data.code).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Municipality code already exists")

    municipality = Municipality(
        name=municipality_data.name,
        code=municipality_data.code,
        region=municipality_data.region,
        external_id=municipality_data.external_id,
        contact_email=municipality_data.contact_email,
        phone=municipality_data.phone,
    )
    db.add(municipality)
    db.commit()
    db.refresh(municipality)
    return municipality


@router.get("/{municipality_id}", response_model=MunicipalityResponse)
def get_municipality(
    municipality_id: int,
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    municipality = db.query(Municipality).filter(Municipality.id == municipality_id).first()
    if municipality is None:
        raise HTTPException(status_code=404, detail="Municipality not found")
    return municipality


@router.get("/{municipality_id}/summary")
def get_municipality_summary(
    municipality_id: int,
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    municipality = db.query(Municipality).filter(Municipality.id == municipality_id).first()
    if municipality is None:
        raise HTTPException(status_code=404, detail="Municipality not found")
    return build_municipality_summary(municipality)


@router.post(
    "/{municipality_id}/service-areas",
    response_model=ServiceAreaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_area(
    municipality_id: int,
    area_data: ServiceAreaCreate,
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    municipality = db.query(Municipality).filter(Municipality.id == municipality_id).first()
    if municipality is None:
        raise HTTPException(status_code=404, detail="Municipality not found")

    existing = (
        db.query(ServiceArea)
        .filter(ServiceArea.municipality_id == municipality_id, ServiceArea.code == area_data.code)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Service area code already exists in this municipality")

    area = ServiceArea(
        municipality_id=municipality.id,
        name=area_data.name,
        code=area_data.code,
        status=area_data.status,
        external_id=area_data.external_id,
        boundary_json=area_data.boundary_json,
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


@router.get("/{municipality_id}/service-areas", response_model=list[ServiceAreaResponse])
def list_service_areas(
    municipality_id: int,
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    municipality = db.query(Municipality).filter(Municipality.id == municipality_id).first()
    if municipality is None:
        raise HTTPException(status_code=404, detail="Municipality not found")
    return db.query(ServiceArea).filter(ServiceArea.municipality_id == municipality_id).order_by(ServiceArea.name.asc()).all()


@router.post("/{municipality_id}/sync")
def trigger_sync(
    municipality_id: int,
    current_user: object = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    municipality = db.query(Municipality).filter(Municipality.id == municipality_id).first()
    if municipality is None:
        raise HTTPException(status_code=404, detail="Municipality not found")

    log = MunicipalSyncLog(
        municipality_id=municipality.id,
        sync_type="service_area_sync",
        provider="internal",
        status="completed",
        details="Municipality sync queued and acknowledged.",
    )
    db.add(log)
    db.commit()
    return {"municipality_id": municipality_id, "status": "completed", "sync_type": "service_area_sync"}
