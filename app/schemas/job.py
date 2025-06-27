from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.job import JobStatus, JobPriority


class ResourceRequirements(BaseModel):
    cpu_units: int = Field(default=1, ge=1, le=16)
    memory_mb: int = Field(default=128, ge=64, le=8192)


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)


class JobCreate(BaseModel):
    type: str = Field(..., min_length=1, max_length=50)
    priority: JobPriority = JobPriority.NORMAL
    payload: Dict[str, Any] = Field(default_factory=dict)
    resource_requirements: ResourceRequirements = Field(
        default_factory=ResourceRequirements
    )
    depends_on: Optional[List[str]] = Field(default=None)  # List of job IDs
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)  # Max 24 hours
    idempotency_key: Optional[str] = Field(default=None, max_length=255)

    @validator("depends_on")
    def validate_depends_on(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError("Cannot depend on more than 10 jobs")
        return v


class JobUpdate(BaseModel):
    priority: Optional[JobPriority] = None
    status: Optional[JobStatus] = None


class JobResponse(BaseModel):
    job_id: UUID
    type: str
    status: JobStatus
    priority: JobPriority
    payload: Dict[str, Any]
    cpu_units: int
    memory_mb: int
    timeout_seconds: int
    max_attempts: int
    current_attempt: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    position_in_queue: Optional[int] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        # Map database field names to response field names
        return cls(
            job_id=obj.id,
            type=obj.type,
            status=obj.status,
            priority=obj.priority,
            payload=obj.payload,
            cpu_units=obj.cpu_units,
            memory_mb=obj.memory_mb,
            timeout_seconds=obj.timeout_seconds,
            max_attempts=obj.max_attempts,
            current_attempt=obj.current_attempt,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            started_at=obj.started_at,
            completed_at=obj.completed_at,
            next_retry_at=obj.next_retry_at,
            result=obj.result,
            error_message=obj.error_message,
        )


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class JobLogResponse(BaseModel):
    id: UUID
    level: str
    message: str
    timestamp: datetime
    context: Optional[str] = None

    model_config = {"from_attributes": True}


class JobLogsResponse(BaseModel):
    logs: List[JobLogResponse]
    total: int
