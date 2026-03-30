"""populations

Revision ID: fdb5a103ebb9
Revises: a2c4f27d2919
Create Date: 2026-03-31 01:11:41.705405

"""
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdb5a103ebb9'
down_revision: Union[str, None] = 'a2c4f27d2919'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

now = datetime.datetime.utcnow()

orders_table = sa.table(
    "orders",
    sa.column("id", sa.Integer),
    sa.column("amount", sa.Integer),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


SEED_ORDERS = [
    {"id": 1, "amount": 50000,  'created_at': now, 'updated_at': now},
    {"id": 2, "amount": 120000, 'created_at': now, 'updated_at': now},
    {"id": 3, "amount": 35050,  'created_at': now, 'updated_at': now},
    {"id": 4, "amount": 999999, 'created_at': now, 'updated_at': now},
    {"id": 5, "amount": 7500,   'created_at': now, 'updated_at': now},
]

def upgrade() -> None:
    op.bulk_insert(orders_table, SEED_ORDERS)


def downgrade() -> None:
    pass
