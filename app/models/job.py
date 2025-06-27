from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Boolean, Float, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as string.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"  # waiting for dependencies
    TIMEOUT = "timeout"


class JobPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Job(Base):
    __tablename__ = "jobs"
    
    # Composite indexes for performance with millions of rows
    __table_args__ = (
        Index('ix_jobs_status_priority_created', 'status', 'priority', 'created_at'),
        Index('ix_jobs_ready_priority_created', 'status', 'priority', 'created_at', 
              postgresql_where=Column('status') == 'ready'),
        Index('ix_jobs_next_retry_at_status', 'next_retry_at', 'status'),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False, index=True)
    status = Column(
        ENUM(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )
    priority = Column(
        ENUM(JobPriority), default=JobPriority.NORMAL, nullable=False, index=True
    )

    # Job payload and configuration
    payload = Column(JSON, nullable=False, default=dict)

    # Resource requirements
    cpu_units = Column(Integer, nullable=False, default=1)
    memory_mb = Column(Integer, nullable=False, default=128)

    # Timing and retry configuration
    timeout_seconds = Column(Integer, nullable=False, default=3600)
    max_attempts = Column(Integer, nullable=False, default=3)
    current_attempt = Column(Integer, nullable=False, default=0)
    backoff_multiplier = Column(Float, nullable=False, default=2.0)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Idempotency
    idempotency_key = Column(String(255), unique=True, nullable=True, index=True)

    # Result and error information
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    dependencies = relationship(
        "JobDependency",
        foreign_keys="JobDependency.child_job_id",
        back_populates="child",
    )
    dependents = relationship(
        "JobDependency",
        foreign_keys="JobDependency.parent_job_id",
        back_populates="parent",
    )
    executions = relationship(
        "JobExecution", back_populates="job", cascade="all, delete-orphan"
    )
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.type}, status={self.status}, priority={self.priority})>"
