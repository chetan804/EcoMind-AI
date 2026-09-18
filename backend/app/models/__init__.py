from app.models.role import Role
from app.models.user import User
from app.models.waste_report import WasteReport
from app.models.collection import WasteCollection
from app.models.route import CollectionRoute, RouteStop
from app.models.complaint import Complaint, ComplaintStatusHistory
from app.models.notification import Notification
from app.models.carbon import CarbonCredit, CarbonTransaction
from app.models.reward import RewardAccount, RewardActivity
from app.models.environmental import (
	EnvironmentalReading,
	EnvironmentalSource,
	SmartBin,
)
from app.models.municipality import Municipality, MunicipalSyncLog, ServiceArea
from app.models.ai_operation import AIOperationLog
from app.models.organization import Organization