from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'interaction_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('service', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
    )
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('meta', sa.Text(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('interaction_logs')