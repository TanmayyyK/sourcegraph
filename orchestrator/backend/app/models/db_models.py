import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from app.core.database import Base

class Asset(Base):
    __tablename__ = 'assets'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    is_golden = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    frames = relationship("FrameVector", back_populates="asset", cascade="all, delete-orphan")

class FrameVector(Base):
    __tablename__ = 'frame_vectors'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id', ondelete='CASCADE'), index=True)
    timestamp = Column(Float, nullable=False)
    
    visual_vector = Column(Vector(512))
    text_vector = Column(Vector(384))
    asset = relationship("Asset", back_populates="frames")

Index(
    'ix_frame_visual_vector_hnsw',
    FrameVector.visual_vector,
    postgresql_using='hnsw',
    postgresql_with={'m': 16, 'ef_construction': 64},
    postgresql_ops={'visual_vector': 'vector_cosine_ops'}
)

Index(
    'ix_frame_text_vector_hnsw',
    FrameVector.text_vector,
    postgresql_using='hnsw',
    postgresql_with={'m': 16, 'ef_construction': 64},
    postgresql_ops={'text_vector': 'vector_cosine_ops'}
)
