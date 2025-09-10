"""Enhanced metadata tables for collection tracking

Revision ID: 002
Revises: 001
Create Date: 2025-01-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add enhanced metadata tables for comprehensive collection tracking."""
    
    # Drop the basic collection_metadata table if it exists
    try:
        op.drop_table('collection_metadata')
    except Exception:
        # Table might not exist, continue
        pass
    
    # Create enhanced collection_metadata table
    op.create_table(
        'collection_metadata',
        sa.Column('collector_type', sa.String(50), primary_key=True),
        sa.Column('last_run', sa.DateTime),
        sa.Column('last_success', sa.DateTime),
        sa.Column('run_count', sa.Integer, default=0),
        sa.Column('error_count', sa.Integer, default=0),
        sa.Column('last_error', sa.Text),
        sa.Column('total_execution_time', sa.Numeric(10, 3), default=0.0),
        sa.Column('total_records_collected', sa.BigInteger, default=0),
        sa.Column('average_execution_time', sa.Numeric(10, 3), default=0.0),
        sa.Column('success_rate', sa.Numeric(5, 2), default=100.0),
        sa.Column('health_score', sa.Numeric(5, 2), default=100.0),
        sa.Column('last_updated', sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    
    # Create execution_history table
    op.create_table(
        'execution_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('collector_type', sa.String(50), nullable=False),
        sa.Column('execution_id', sa.String(100), nullable=False, unique=True),
        sa.Column('start_time', sa.DateTime, nullable=False),
        sa.Column('end_time', sa.DateTime),
        sa.Column('status', sa.String(20), nullable=False),  # success, failure, partial, timeout, cancelled
        sa.Column('records_collected', sa.Integer, default=0),
        sa.Column('execution_time', sa.Numeric(10, 3)),  # in seconds
        sa.Column('error_message', sa.Text),
        sa.Column('warnings', sa.Text),  # JSON array of warnings
        sa.Column('execution_metadata', sa.Text),  # JSON metadata
        sa.Column('created_at', sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    
    # Create performance_metrics table
    op.create_table(
        'performance_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('collector_type', sa.String(50), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Numeric(20, 8), nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('labels', sa.Text),  # JSON labels
        sa.Column('created_at', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('collector_type', 'metric_name', 'timestamp', name='uq_metrics_collector_metric_timestamp'),
    )
    
    # Create system_alerts table
    op.create_table(
        'system_alerts',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('alert_id', sa.String(100), nullable=False, unique=True),
        sa.Column('level', sa.String(20), nullable=False),  # info, warning, error, critical
        sa.Column('collector_type', sa.String(50), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('acknowledged', sa.Boolean, default=False),
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('alert_metadata', sa.Text),  # JSON metadata
        sa.Column('created_at', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    
    # Create indexes for better query performance
    op.create_index('idx_execution_history_collector_time', 'execution_history', ['collector_type', 'start_time'])
    op.create_index('idx_execution_history_status', 'execution_history', ['status'])
    op.create_index('idx_performance_metrics_collector_metric', 'performance_metrics', ['collector_type', 'metric_name'])
    op.create_index('idx_performance_metrics_timestamp', 'performance_metrics', ['timestamp'])
    op.create_index('idx_system_alerts_level', 'system_alerts', ['level'])
    op.create_index('idx_system_alerts_collector', 'system_alerts', ['collector_type'])
    op.create_index('idx_system_alerts_resolved', 'system_alerts', ['resolved'])
    op.create_index('idx_system_alerts_timestamp', 'system_alerts', ['timestamp'])


def downgrade() -> None:
    """Drop enhanced metadata tables."""
    
    # Drop indexes first
    op.drop_index('idx_system_alerts_timestamp')
    op.drop_index('idx_system_alerts_resolved')
    op.drop_index('idx_system_alerts_collector')
    op.drop_index('idx_system_alerts_level')
    op.drop_index('idx_performance_metrics_timestamp')
    op.drop_index('idx_performance_metrics_collector_metric')
    op.drop_index('idx_execution_history_status')
    op.drop_index('idx_execution_history_collector_time')
    
    # Drop tables
    op.drop_table('system_alerts')
    op.drop_table('performance_metrics')
    op.drop_table('execution_history')
    op.drop_table('collection_metadata')
    
    # Recreate basic collection_metadata table
    op.create_table(
        'collection_metadata',
        sa.Column('collector_type', sa.String(50), primary_key=True),
        sa.Column('last_run', sa.DateTime),
        sa.Column('last_success', sa.DateTime),
        sa.Column('run_count', sa.Integer, default=0),
        sa.Column('error_count', sa.Integer, default=0),
        sa.Column('last_error', sa.Text),
    )