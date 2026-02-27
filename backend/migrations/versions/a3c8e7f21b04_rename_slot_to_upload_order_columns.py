"""rename slot to upload order columns

Revision ID: a3c8e7f21b04
Revises: 5b77a1c3f39e
Create Date: 2026-02-27 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3c8e7f21b04'
down_revision: Union[str, None] = '5b77a1c3f39e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'run_telemetry',
        'intended_slot_plan_json',
        new_column_name='intended_upload_order_json',
    )
    op.alter_column(
        'run_telemetry',
        'slot_mismatch_json',
        new_column_name='allocation_analysis_json',
    )


def downgrade() -> None:
    op.alter_column(
        'run_telemetry',
        'intended_upload_order_json',
        new_column_name='intended_slot_plan_json',
    )
    op.alter_column(
        'run_telemetry',
        'allocation_analysis_json',
        new_column_name='slot_mismatch_json',
    )
