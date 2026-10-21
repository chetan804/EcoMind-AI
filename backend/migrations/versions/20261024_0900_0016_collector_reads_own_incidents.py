"""Let collectors see the community incidents they reported.

Revision ID: 0016

Found by the project audit: a collector holds ``incidents:create`` (they may report a problem from
the field) but not ``incidents:read_own``, so the Incidents screen answered 403 for a collector who
only holds that role. The grant is a literal copy of what ``app.modules.users.rbac`` defines at this
revision (migrations never import application code). Only the collector grant is added; nobody
gains access to incidents reported by other people.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = "collector"
CODE = "incidents:read_own"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.name = :role AND p.code = :code ON CONFLICT DO NOTHING"
        ),
        {"role": ROLE, "code": CODE},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role_id = (SELECT id FROM roles WHERE name = :role) "
            "AND permission_id = (SELECT id FROM permissions WHERE code = :code)"
        ),
        {"role": ROLE, "code": CODE},
    )
