from alembic import op
import sqlalchemy as sa
import app.models

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('rate_limit_buckets',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('window_start', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('seed_markers',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('completed_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('manager_id', sa.Integer(), nullable=True),
    sa.Column('password_hash', sa.String(length=512), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('employee','manager')", name='ck_user_role'),
    sa.CheckConstraint('manager_id IS NULL OR manager_id != id', name='ck_not_self_manager'),
    sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_manager_id'), 'users', ['manager_id'], unique=False)
    op.create_table('attendance',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.String(length=36), nullable=False),
    sa.Column('start_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('end_at', app.models.UTCDateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.CheckConstraint('end_at IS NULL OR end_at > start_at', name='ck_positive_interval'),
    sa.CheckConstraint('version >= 1', name='ck_entry_version'),
    sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id', 'request_id', name='uq_employee_request')
    )
    op.create_index('ix_entry_employee_start', 'attendance', ['employee_id', 'start_at'], unique=False)
    op.create_index('uq_one_active_entry', 'attendance', ['employee_id'], unique=True, postgresql_where=sa.text('end_at IS NULL'), sqlite_where=sa.text('end_at IS NULL'))
    op.create_table('sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('created_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('expires_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_sessions_expires_at'), 'sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('corrections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('original_start', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('original_end', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('proposed_start', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('proposed_end', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('base_entry_version', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.Column('decided_at', app.models.UTCDateTime(timezone=True), nullable=True),
    sa.Column('decided_by_id', sa.Integer(), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=True),
    sa.CheckConstraint("state IN ('pending','approved','rejected','withdrawn')", name='ck_correction_state'),
    sa.CheckConstraint('proposed_end > proposed_start', name='ck_correction_interval'),
    sa.CheckConstraint('original_end > original_start', name='ck_correction_original_interval'),
    sa.CheckConstraint('version >= 1', name='ck_correction_version'),
    sa.ForeignKeyConstraint(['decided_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['entry_id'], ['attendance.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_corrections_employee_id'), 'corrections', ['employee_id'], unique=False)
    op.create_index(op.f('ix_corrections_entry_id'), 'corrections', ['entry_id'], unique=False)
    op.create_index('uq_one_pending_correction', 'corrections', ['entry_id'], unique=True, postgresql_where=sa.text("state = 'pending'"), sqlite_where=sa.text("state = 'pending'"))
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('summary', sa.String(length=500), nullable=False),
    sa.Column('created_at', app.models.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['entry_id'], ['attendance.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_entry_id'), 'events', ['entry_id'], unique=False)

def downgrade():
    raise RuntimeError('Destructive downgrade is disabled; restore a verified backup instead')
