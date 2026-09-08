from app.models.municipality import Municipality, ServiceArea


def build_municipality_summary(municipality: Municipality) -> dict[str, int | str]:
    total_service_areas = len(municipality.service_areas)
    active_service_areas = sum(
        1 for area in municipality.service_areas if area.status == "active"
    )
    return {
        "name": municipality.name,
        "code": municipality.code,
        "region": municipality.region,
        "total_service_areas": total_service_areas,
        "active_service_areas": active_service_areas,
        "is_active": municipality.is_active,
    }


def create_service_area(municipality: Municipality, name: str, code: str, status: str = "active") -> ServiceArea:
    area = ServiceArea(
        municipality_id=municipality.id,
        name=name,
        code=code,
        status=status,
    )
    municipality.service_areas.append(area)
    return area
