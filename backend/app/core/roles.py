from enum import IntEnum, StrEnum


class RoleID(IntEnum):
    ADMIN = 4
    CITIZEN = 5
    COLLECTOR = 6


class RoleName(StrEnum):
    ADMIN = "admin"
    CITIZEN = "citizen"
    COLLECTOR = "collector"


ROLE_NAMES = {
    RoleID.ADMIN: RoleName.ADMIN,
    RoleID.CITIZEN: RoleName.CITIZEN,
    RoleID.COLLECTOR: RoleName.COLLECTOR,
}


def is_valid_role_id(role_id: int) -> bool:
    return role_id in ROLE_NAMES


def role_name_for_id(role_id: int) -> RoleName | None:
    return ROLE_NAMES.get(RoleID(role_id)) if role_id in ROLE_NAMES else None
