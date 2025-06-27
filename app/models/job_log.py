from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app.models.job import GUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(GUID(), primary_key=True, default=lambda: __import__("uuid").uuid4())
    job_id = Column(
        GUID(),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level = Column(ENUM(LogLevel), nullable=False, default=LogLevel.INFO)
    message = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Optional context
    context = Column(String(255), nullable=True)  # e.g., "scheduler", "worker", "api"

    # Relationships
    job = relationship("Job", back_populates="logs")

    def __repr__(self):
        return f"<JobLog(id={self.id}, job_id={self.job_id}, level={self.level})>"
