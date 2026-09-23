"""Aggregator: importing every model ensures metadata completeness and that the
tenant-isolation registry sees all tenant-scoped tables before any query runs."""

from app.ai.models import AiInference, AiReview
from app.audit.models import AuditEvent
from app.auth.models import Permission, RefreshToken, Role, User, PasswordResetToken, role_permissions
from app.collection.models import (
    CollectionEvent,
    CollectionPoint,
    CollectionSchedule,
    EventStatus,
    PointKind,
    ScheduleFrequency,
)
from app.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintComment,
    ComplaintPriority,
    ComplaintStatus,
)
from app.core.db import Base
from app.fleet.models import DriverProfile, FuelType, Vehicle, VehicleStatus, VehicleType
from app.iot.models import (
    Alert,
    AlertRule,
    AlertRuleMetric,
    AlertSeverity,
    AlertStatus,
    Device,
    DeviceKind,
    DeviceStatus,
    TelemetryReading,
    TelemetrySource,
)
from app.jobs.models import Job, JobStatus
from app.media.models import MediaAsset, MediaKind, ScanStatus
from app.notifications.models import Notification, NotificationCategory
from app.orgs.models import (
    OperationalUnit,
    OrgInvitation,
    OrgMembership,
    OrgStatus,
    OrgType,
    OrgUsageCounters,
    Organization,
    Zone,
)
from app.rewards.models import RewardLedger, RewardReason
from app.routing.models import Route, RouteStatus, RouteStop, StopStatus
from app.sustainability.models import (
    CarbonRecord,
    DataQuality,
    EmissionFactor,
    EmissionScope,
    FactorCategory,
    WasteTreatment,
)
from app.waste.models import (
    ReportSeverity,
    ReportSource,
    ReportStatus,
    WasteCategory,
    WasteReport,
    WasteReportEvent,
)

__all__ = [
    "Base",
    # orgs / identity
    "Organization", "OrgType", "OrgStatus", "OperationalUnit", "Zone",
    "OrgMembership", "OrgInvitation", "OrgUsageCounters",
    "User", "Role", "Permission", "role_permissions", "RefreshToken", "PasswordResetToken",
    # waste
    "WasteCategory", "WasteReport", "WasteReportEvent", "ReportStatus", "ReportSeverity", "ReportSource",
    # complaints
    "Complaint", "ComplaintComment", "ComplaintCategory", "ComplaintStatus", "ComplaintPriority",
    # collection
    "CollectionPoint", "CollectionSchedule", "CollectionEvent", "PointKind", "ScheduleFrequency", "EventStatus",
    # fleet
    "Vehicle", "DriverProfile", "VehicleType", "FuelType", "VehicleStatus",
    # routing
    "Route", "RouteStop", "RouteStatus", "StopStatus",
    # iot
    "Device", "TelemetryReading", "AlertRule", "Alert", "DeviceKind", "DeviceStatus",
    "TelemetrySource", "AlertRuleMetric", "AlertSeverity", "AlertStatus",
    # ai
    "AiInference", "AiReview",
    # media
    "MediaAsset", "MediaKind", "ScanStatus",
    # sustainability
    "EmissionFactor", "CarbonRecord", "WasteTreatment", "FactorCategory", "EmissionScope", "DataQuality",
    # notifications / rewards / audit / jobs
    "Notification", "NotificationCategory", "RewardLedger", "RewardReason", "AuditEvent", "Job", "JobStatus",
]
