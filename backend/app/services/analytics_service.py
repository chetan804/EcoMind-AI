from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.roles import RoleID
from app.models.collection import WasteCollection
from app.models.complaint import Complaint
from app.models.user import User
from app.models.waste_report import WasteReport


def dashboard_stats(db: Session) -> dict[str, int]:
    total_users = db.query(func.count(User.id)).scalar() or 0
    citizens = (
        db.query(func.count(User.id))
        .filter(User.role_id == int(RoleID.CITIZEN))
        .scalar()
        or 0
    )
    collectors = (
        db.query(func.count(User.id))
        .filter(User.role_id == int(RoleID.COLLECTOR))
        .scalar()
        or 0
    )
    total_reports = db.query(func.count(WasteReport.id)).scalar() or 0
    pending_reports = (
        db.query(func.count(WasteReport.id))
        .filter(WasteReport.status.notin_(["collected", "resolved"]))
        .scalar()
        or 0
    )
    completed_collections = (
        db.query(func.count(WasteCollection.id))
        .filter(WasteCollection.status == "collected")
        .scalar()
        or 0
    )
    pending_collections = (
        db.query(func.count(WasteCollection.id))
        .filter(WasteCollection.status.in_(["assigned", "in_progress"]))
        .scalar()
        or 0
    )
    total_complaints = db.query(func.count(Complaint.id)).scalar() or 0
    unresolved_complaints = (
        db.query(func.count(Complaint.id))
        .filter(Complaint.status.notin_(["resolved", "rejected"]))
        .scalar()
        or 0
    )
    return {
        "total_users": total_users,
        "citizens": citizens,
        "collectors": collectors,
        "total_reports": total_reports,
        "pending_reports": pending_reports,
        "completed_collections": completed_collections,
        "pending_collections": pending_collections,
        "total_complaints": total_complaints,
        "unresolved_complaints": unresolved_complaints,
    }


def waste_distribution(db: Session) -> list[dict[str, int | str]]:
    rows = (
        db.query(WasteReport.waste_type, func.count(WasteReport.id))
        .group_by(WasteReport.waste_type)
        .order_by(func.count(WasteReport.id).desc())
        .all()
    )
    return [{"label": waste_type, "count": count} for waste_type, count in rows]
