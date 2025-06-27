from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app.models.job import GUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class ExecutionStatus(str, enum.Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class JobExecution(Base):
    __tablename__ = "job_executions"

    id = Column(GUID(), primary_key=True, default=lambda: __import__("uuid").uuid4())
    job_id = Column(
        GUID(),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number = Column(Integer, nullable=False)
    status = Column(ENUM(ExecutionStatus), nullable=False)

    # Timing
    started_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Worker information
    worker_id = Column(String(255), nullable=True)
    worker_hostname = Column(String(255), nullable=True)

    # Execution details
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="executions")

    def __repr__(self):
        return f"<JobExecution(id={self.id}, job_id={self.job_id}, attempt={self.attempt_number}, status={self.status})>"
