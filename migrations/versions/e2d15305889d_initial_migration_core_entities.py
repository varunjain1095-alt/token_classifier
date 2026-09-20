"""Initial migration - core entities

Revision ID: e2d15305889d
Revises: 
Create Date: 2026-09-18 20:43:30.070931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2d15305889d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sources table
    op.create_table('sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('format_adapter', sa.String(length=100), nullable=True),
        sa.Column('file_reference', sa.Text(), nullable=True),
        sa.Column('connection_reference', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create dataset_snapshots table
    op.create_table('dataset_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extraction_start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extraction_end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('selection_filter_specification', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('exact_captured_count', sa.Integer(), nullable=True),
        sa.Column('eligibility_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('consistency_mode', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create review_records table
    op.create_table('review_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_source_id', sa.String(length=255), nullable=True),
        sa.Column('original_review_text', sa.Text(), nullable=False),
        sa.Column('mapped_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_row_locator', sa.String(length=255), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('eligibility_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['dataset_snapshots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create workload_versions table
    op.create_table('workload_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('selection_mode', sa.String(length=50), nullable=False),
        sa.Column('requested_percentage', sa.Float(), nullable=True),
        sa.Column('requested_count', sa.Integer(), nullable=True),
        sa.Column('rounding_rule', sa.String(length=50), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True),
        sa.Column('ordered_record_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolved_count', sa.Integer(), nullable=True),
        sa.Column('review_text_token_total', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['dataset_snapshots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_sources_created_by', 'sources', ['created_by'])
    op.create_index('idx_dataset_snapshots_source_id', 'dataset_snapshots', ['source_id'])
    op.create_index('idx_review_records_snapshot_id', 'review_records', ['snapshot_id'])
    op.create_index('idx_workload_versions_snapshot_id', 'workload_versions', ['snapshot_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_workload_versions_snapshot_id', table_name='workload_versions')
    op.drop_index('idx_review_records_snapshot_id', table_name='review_records')
    op.drop_index('idx_dataset_snapshots_source_id', table_name='dataset_snapshots')
    op.drop_index('idx_sources_created_by', table_name='sources')
    
    # Drop tables
    op.drop_table('workload_versions')
    op.drop_table('review_records')
    op.drop_table('dataset_snapshots')
    op.drop_table('sources')
