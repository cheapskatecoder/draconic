from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.models import Job, JobStatus, JobPriority, JobLog
from app.schemas import (
    JobCreate,
    JobResponse,
    JobUpdate,
    JobListResponse,
    JobLogsResponse,
)
from app.services.job_service import JobService
from app.services.dependency_service import DependencyService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=JobResponse)
async def create_job(job_data: JobCreate, db: AsyncSession = Depends(get_db)):
    """Submit a new job to the queue."""
    try:
        job_service = JobService(db)

        # Check for circular dependencies if depends_on is provided
        if job_data.depends_on:
            dependency_service = DependencyService(db)
            for dep_id in job_data.depends_on:
                if not await dependency_service.job_exists(dep_id):
                    raise HTTPException(
                        status_code=400, detail=f"Dependency job {dep_id} not found"
                    )

        job = await job_service.create_job(job_data)

        # Calculate position in queue
        position = await job_service.get_queue_position(job.id)

        response = JobResponse.from_orm(job)
        response.position_in_queue = position

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get job status and details."""
    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Calculate position in queue if job is pending/ready
    position = None
    if job.status in [JobStatus.PENDING, JobStatus.READY, JobStatus.BLOCKED]:
        position = await job_service.get_queue_position(job.id)

    response = JobResponse.from_orm(job)
    response.position_in_queue = position

    return response


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[JobStatus] = None,
    priority: Optional[JobPriority] = None,
    job_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List jobs with filtering and pagination."""
    job_service = JobService(db)

    jobs, total = await job_service.list_jobs(
        page=page,
        per_page=per_page,
        status=status,
        priority=priority,
        job_type=job_type,
    )

    job_responses = []
    for job in jobs:
        position = None
        if job.status in [JobStatus.PENDING, JobStatus.READY, JobStatus.BLOCKED]:
            position = await job_service.get_queue_position(job.id)

        response = JobResponse.from_orm(job)
        response.position_in_queue = position
        job_responses.append(response)

    return JobListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_next=page * per_page < total,
        has_prev=page > 1,
    )


@router.patch("/{job_id}/cancel")
async def cancel_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Cancel a job if possible."""
    job_service = JobService(db)

    success = await job_service.cancel_job(job_id)

    if not success:
        job = await job_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status == JobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Cannot cancel completed job")
        elif job.status == JobStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Cannot cancel running job")
        elif job.status == JobStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Job already cancelled")
        else:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")

    return {"message": "Job cancelled successfully"}


@router.get("/{job_id}/logs", response_model=JobLogsResponse)
async def get_job_logs(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get job execution logs."""
    job_service = JobService(db)

    # Check if job exists
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get logs
    query = (
        select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.timestamp.desc())
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    return JobLogsResponse(logs=[log for log in logs], total=len(logs))
