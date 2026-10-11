from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

"""Initial schema: customers, devices, measurements.

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column[datetime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("email", name=op.f("uq_customers_email")),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("serial_number", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "INACTIVE",
                "FAULTY",
                name="device_status",
                native_enum=False,
                length=16,
                create_constraint=False,
            ),
            nullable=False,
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'FAULTY')",
            name=op.f("ck_devices_device_status"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_devices_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("serial_number", name=op.f("uq_devices_serial_number")),
    )
    op.create_index(op.f("ix_devices_customer_id"), "devices", ["customer_id"], unique=False)

    op.create_table(
        "measurements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        _timestamp("created_at"),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_measurements_device_id_devices"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_measurements")),
        # The natural key that makes ingestion idempotent (see kamleon/ingestion/service.py).
        sa.UniqueConstraint(
            "device_id",
            "type",
            "timestamp",
            name=op.f("uq_measurements_device_id_type_timestamp"),
        ),
    )
    op.create_index(
        "ix_measurements_device_id_timestamp",
        "measurements",
        ["device_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_measurements_device_id_timestamp", table_name="measurements")
    op.drop_table("measurements")
    op.drop_index(op.f("ix_devices_customer_id"), table_name="devices")
    op.drop_table("devices")
    op.drop_table("customers")
