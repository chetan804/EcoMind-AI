from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.roles import RoleID
from app.core.security import require_role
from app.db.database import get_db
from app.models.environmental import EnvironmentalReading, EnvironmentalSource, SmartBin
from app.models.user import User
from app.schemas.environmental import (
    EnvironmentalReadingCreate,
    EnvironmentalSourceCreate,
    EnvironmentalSourceResponse,
    SmartBinCreate,
    SmartBinResponse,
    SmartBinUpdate,
)


router = APIRouter(prefix="/environmental", tags=["Environmental Monitoring"])


@router.get("/sources", response_model=list[EnvironmentalSourceResponse])
def list_sources(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return (
        db.query(EnvironmentalSource)
        .options(selectinload(EnvironmentalSource.readings))
        .order_by(EnvironmentalSource.created_at.desc())
        .all()
    )


@router.post("/sources", response_model=EnvironmentalSourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(
    source_data: EnvironmentalSourceCreate,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    source = EnvironmentalSource(**source_data.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.post("/sources/{source_id}/readings", response_model=EnvironmentalSourceResponse, status_code=status.HTTP_201_CREATED)
def add_reading(
    source_id: int,
    reading_data: EnvironmentalReadingCreate,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    source = db.query(EnvironmentalSource).filter(EnvironmentalSource.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Environmental source not found")
    source.readings.append(EnvironmentalReading(**reading_data.model_dump()))
    db.commit()
    db.refresh(source)
    return source


@router.get("/bins", response_model=list[SmartBinResponse])
def list_smart_bins(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return db.query(SmartBin).order_by(SmartBin.created_at.desc()).all()


@router.post("/bins", response_model=SmartBinResponse, status_code=status.HTTP_201_CREATED)
def register_smart_bin(
    bin_data: SmartBinCreate,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    existing = db.query(SmartBin).filter(SmartBin.bin_code == bin_data.bin_code).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bin code already registered")
    smart_bin = SmartBin(**bin_data.model_dump())
    db.add(smart_bin)
    db.commit()
    db.refresh(smart_bin)
    return smart_bin


@router.patch("/bins/{bin_id}", response_model=SmartBinResponse)
def update_smart_bin(
    bin_id: int,
    update_data: SmartBinUpdate,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    smart_bin = db.query(SmartBin).filter(SmartBin.id == bin_id).first()
    if smart_bin is None:
        raise HTTPException(status_code=404, detail="Smart bin not found")
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(smart_bin, field, value)
    smart_bin.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(smart_bin)
    return smart_bin
