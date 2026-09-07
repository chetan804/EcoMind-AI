from enum import IntEnum


class RoleID(IntEnum):
    ADMIN = 4
    CITIZEN = 5
    COLLECTOR = 6


ROLE_NAMES = {
    RoleID.ADMIN: "admin",
    RoleID.CITIZEN: "citizen",
    RoleID.COLLECTOR: "collector",
}


def is_valid_role_id(role_id: int) -> bool:
    return role_id in ROLE_NAMES
