from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int
    citizens: int
    collectors: int
    total_reports: int
    pending_reports: int
    completed_collections: int
    pending_collections: int
    total_complaints: int
    unresolved_complaints: int


class DistributionItem(BaseModel):
    label: str
    count: int
