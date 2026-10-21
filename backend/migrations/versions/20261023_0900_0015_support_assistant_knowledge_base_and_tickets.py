"""Help assistant: knowledge base, transcripts, support tickets, and their permissions.

Revision ID: 0015
Revises: 0014

``knowledge_articles.search_vector`` is a stored generated column (PostgreSQL full-text search,
no extension needed) with a GIN index. No article is seeded here: the shipped platform help lives
in ``app/modules/support/knowledge/platform_help.json`` and is loaded by the CLI command
``seed-support-knowledge``, so it can be revised without a migration.

The permission and role-grant rows are literal copies of what ``app.modules.users.rbac`` defines at
this revision (migrations never import application code).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "support:ask": "Ask the help assistant and open support tickets",
    "support:manage": "Answer, assign and close every support ticket",
    "knowledge:manage": "Write and publish help articles",
}
ALL_ROLES = ("citizen", "collector", "facility_operator", "manager", "administrator")
STAFF_ROLES = ("manager", "administrator")
GRANTS = {
    "support:ask": ALL_ROLES,
    "support:manage": STAFF_ROLES,
    "knowledge:manage": STAFF_ROLES,
}


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assistant_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_conversations")),
    )
    op.create_index(
        op.f("ix_assistant_conversations_user_id"),
        "assistant_conversations",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "knowledge_articles",
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("keywords", sa.Text(), server_default="", nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("published", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || setweight(to_tsvector('english', coalesce(body, '')), 'B') || setweight(to_tsvector('english', coalesce(keywords, '')), 'C')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_knowledge_articles_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name=op.f("fk_knowledge_articles_updated_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_articles")),
        sa.UniqueConstraint("slug", name=op.f("uq_knowledge_articles_slug")),
    )
    op.create_index(
        op.f("ix_knowledge_articles_category"), "knowledge_articles", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_articles_created_by_id"),
        "knowledge_articles",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_articles_published"), "knowledge_articles", ["published"], unique=False
    )
    op.create_index(
        "ix_knowledge_articles_search_vector",
        "knowledge_articles",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_knowledge_articles_updated_by_id"),
        "knowledge_articles",
        ["updated_by_id"],
        unique=False,
    )
    op.create_table(
        "assistant_messages",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", name="messagerole", native_enum=False, length=17),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum(
                "question",
                "knowledge",
                "account_data",
                "no_answer",
                "not_permitted",
                name="messagekind",
                native_enum=False,
                length=21,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "sources", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("helpful", sa.Boolean(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('question', 'knowledge', 'account_data', 'no_answer', 'not_permitted')",
            name=op.f("ck_assistant_messages_kind_valid"),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name=op.f("ck_assistant_messages_role_valid")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["assistant_conversations.id"],
            name=op.f("fk_assistant_messages_conversation_id_assistant_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_messages")),
    )
    op.create_index(
        op.f("ix_assistant_messages_conversation_id"),
        "assistant_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_table(
        "support_tickets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "in_progress",
                "resolved",
                "closed",
                name="ticketstatus",
                native_enum=False,
                length=19,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column("assignee_id", sa.UUID(), nullable=True),
        sa.Column("shared_conversation_id", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')",
            name=op.f("ck_support_tickets_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.id"], name=op.f("fk_support_tickets_assignee_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["shared_conversation_id"],
            ["assistant_conversations.id"],
            name=op.f("fk_support_tickets_shared_conversation_id_assistant_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_support_tickets_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_tickets")),
    )
    op.create_index(
        op.f("ix_support_tickets_assignee_id"), "support_tickets", ["assignee_id"], unique=False
    )
    op.create_index(
        op.f("ix_support_tickets_shared_conversation_id"),
        "support_tickets",
        ["shared_conversation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_support_tickets_status"), "support_tickets", ["status"], unique=False)
    op.create_index(
        op.f("ix_support_tickets_user_id"), "support_tickets", ["user_id"], unique=False
    )
    op.create_table(
        "support_ticket_replies",
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_support_ticket_replies_author_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_support_ticket_replies_ticket_id_support_tickets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_ticket_replies")),
    )
    op.create_index(
        op.f("ix_support_ticket_replies_author_id"),
        "support_ticket_replies",
        ["author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_ticket_replies_ticket_id"),
        "support_ticket_replies",
        ["ticket_id"],
        unique=False,
    )
    connection = op.get_bind()
    for code, description in PERMISSIONS.items():
        connection.execute(
            sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
            {"code": code, "description": description},
        )
        for role in GRANTS[code]:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.name = :role AND p.code = :code ON CONFLICT DO NOTHING"
                ),
                {"role": role, "code": code},
            )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(PERMISSIONS)}
    )
    op.drop_index(op.f("ix_support_ticket_replies_ticket_id"), table_name="support_ticket_replies")
    op.drop_index(op.f("ix_support_ticket_replies_author_id"), table_name="support_ticket_replies")
    op.drop_table("support_ticket_replies")
    op.drop_index(op.f("ix_support_tickets_user_id"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_status"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_shared_conversation_id"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_assignee_id"), table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index(op.f("ix_assistant_messages_conversation_id"), table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index(op.f("ix_knowledge_articles_updated_by_id"), table_name="knowledge_articles")
    op.drop_index(
        "ix_knowledge_articles_search_vector",
        table_name="knowledge_articles",
        postgresql_using="gin",
    )
    op.drop_index(op.f("ix_knowledge_articles_published"), table_name="knowledge_articles")
    op.drop_index(op.f("ix_knowledge_articles_created_by_id"), table_name="knowledge_articles")
    op.drop_index(op.f("ix_knowledge_articles_category"), table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
    op.drop_index(op.f("ix_assistant_conversations_user_id"), table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
