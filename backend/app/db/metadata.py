"""Explicit metadata registration for Alembic.

Every module that owns tables must be imported here, otherwise ``alembic revision
--autogenerate`` cannot see its tables. The import order is the module dependency order
(see docs/architecture/component-boundaries.md): a module only references tables of modules
listed before it.
"""

from __future__ import annotations

from app.db.base import Base
from app.modules.anomaly_detection import models as anomaly_detection_models
from app.modules.audit import models as audit_models
from app.modules.auth import models as auth_models
from app.modules.circular_economy import models as circular_economy_models
from app.modules.classification import models as classification_models
from app.modules.collection import models as collection_models
from app.modules.community_incidents import models as community_incidents_models
from app.modules.facilities import models as facilities_models
from app.modules.fleet import models as fleet_models
from app.modules.forecasting import models as forecasting_models
from app.modules.marketplace import models as marketplace_models
from app.modules.material_passports import models as material_passports_models
from app.modules.notifications import models as notifications_models
from app.modules.rewards import models as rewards_models
from app.modules.route_planning import models as route_planning_models
from app.modules.sorting_guide import models as sorting_guide_models
from app.modules.users import models as users_models
from app.modules.waste_reports import models as waste_reports_models

_REGISTERED_MODEL_MODULES = (
    users_models,
    auth_models,
    sorting_guide_models,
    facilities_models,
    fleet_models,
    waste_reports_models,
    classification_models,
    collection_models,
    route_planning_models,
    circular_economy_models,
    material_passports_models,
    community_incidents_models,
    marketplace_models,
    rewards_models,
    notifications_models,
    forecasting_models,
    anomaly_detection_models,
    audit_models,
)

target_metadata = Base.metadata

__all__ = ["target_metadata"]
