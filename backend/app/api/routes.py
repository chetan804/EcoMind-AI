from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import RoleID
from app.core.security import get_current_user, require_role
from app.db.database import get_db
from app.models.collection import WasteCollection
from app.models.route import CollectionRoute, RouteStop
from app.models.user import User
from app.schemas.route import RouteResponse
from app.services.route_optimizer import optimize_collections


router = APIRouter(prefix="/routes", tags=["Collection Routes"])


@router.post(
    "/generate/{collector_id}",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_route(
    collector_id: int,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    collector = (
        db.query(User)
        .filter(
            User.id == collector_id,
            User.role_id == int(RoleID.COLLECTOR),
            User.is_active.is_(True),
        )
        .first()
    )
    if collector is None:
        raise HTTPException(status_code=404, detail="Collector not found")

    collections = (
        db.query(WasteCollection)
        .filter(
            WasteCollection.collector_id == collector_id,
            WasteCollection.status.in_(["assigned", "in_progress"]),
            ~WasteCollection.route_stops.any(),
        )
        .all()
    )
    plan = optimize_collections(collections)
    route = CollectionRoute(
        collector_id=collector_id,
        status="generated",
        estimated_distance_km=round(plan.total_distance_km, 3),
        estimated_duration_minutes=round(plan.estimated_duration_minutes, 1),
    )
    route.stops = [
        RouteStop(
            collection=stop.collection,
            stop_order=stop.stop_order,
            distance_from_previous_km=round(
                stop.distance_from_previous_km,
                3,
            ),
        )
        for stop in plan.stops
    ]
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.get("/my-routes", response_model=list[RouteResponse])
def get_my_routes(
    current_user: User = Depends(require_role(RoleID.COLLECTOR)),
    db: Session = Depends(get_db),
):
    return (
        db.query(CollectionRoute)
        .filter(CollectionRoute.collector_id == current_user.id)
        .order_by(CollectionRoute.created_at.desc())
        .all()
    )


@router.get("/admin/all", response_model=list[RouteResponse])
def get_all_routes(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return db.query(CollectionRoute).order_by(CollectionRoute.created_at.desc()).all()


@router.get("/{route_id}", response_model=RouteResponse)
def get_route(
    route_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    route = db.query(CollectionRoute).filter(CollectionRoute.id == route_id).first()
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    if current_user.role_id != int(RoleID.ADMIN) and route.collector_id != current_user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return route
