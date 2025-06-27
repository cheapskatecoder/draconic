from sqlalchemy import Column, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.job import GUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class JobDependency(Base):
    __tablename__ = "job_dependencies"

    id = Column(GUID(), primary_key=True, default=lambda: __import__("uuid").uuid4())
    parent_job_id = Column(
        GUID(), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    child_job_id = Column(
        GUID(), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    parent = relationship(
        "Job", foreign_keys=[parent_job_id], back_populates="dependents"
    )
    child = relationship(
        "Job", foreign_keys=[child_job_id], back_populates="dependencies"
    )

    # Ensure we don't have duplicate dependencies
    __table_args__ = (
        UniqueConstraint("parent_job_id", "child_job_id", name="unique_dependency"),
    )

    def __repr__(self):
        return (
            f"<JobDependency(parent={self.parent_job_id}, child={self.child_job_id})>"
        )
