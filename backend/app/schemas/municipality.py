from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceAreaResponse(BaseModel):
    id: int
    municipality_id: int
    name: str
    code: str
    status: str
    external_id: str | None = None
    boundary_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MunicipalityResponse(BaseModel):
    id: int
    name: str
    code: str
    region: str
    external_id: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    service_areas: list[ServiceAreaResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MunicipalityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=2, max_length=30)
    region: str = Field(min_length=2, max_length=120)
    external_id: str | None = Field(default=None, max_length=80)
    contact_email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=40)


class ServiceAreaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=2, max_length=30)
    status: str = Field(default="active", max_length=30)
    external_id: str | None = Field(default=None, max_length=80)
    boundary_json: str | None = None
