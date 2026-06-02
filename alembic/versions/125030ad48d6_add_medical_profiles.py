"""add medical_profiles

Revision ID: 125030ad48d6
Revises: 7929718f7fb9
Create Date: 2026-06-02 15:17:04.260803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '125030ad48d6'
down_revision: Union[str, Sequence[str], None] = '7929718f7fb9'
branch_labels= None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
          "medical_profiles",
          sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
          sa.Column("patient_id", sa.Uuid(), nullable=False),
          sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()),
                    server_default=sa.text("'{}'::jsonb"), nullable=False),
          sa.Column("last_source", sa.String(length=100), nullable=True),
          sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
          sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
          sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
          sa.PrimaryKeyConstraint("id"),
          sa.UniqueConstraint("patient_id", name="uq_medical_profiles_patient"),
      )

    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("medical_profiles")
    pass
