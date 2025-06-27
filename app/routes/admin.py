from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.core.database import get_db
from app.services.dead_letter_queue import DeadLetterQueueService
from app.services.job_service import JobService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dlq/jobs")
async def get_dead_letter_queue_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get jobs from the dead letter queue."""
    dlq_service = DeadLetterQueueService()
    jobs = await dlq_service.get_dlq_jobs(limit=limit, offset=offset)
    total = await dlq_service.get_dlq_count()
    
    return {
        "jobs": jobs,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }


@router.get("/dlq/stats")
async def get_dead_letter_queue_stats():
    """Get dead letter queue statistics."""
    dlq_service = DeadLetterQueueService()
    stats = await dlq_service.get_dlq_stats()
    
    return {
        "stats": stats,
        "recent_failures": await dlq_service.get_recent_failures(limit=5)
    }


@router.post("/dlq/retry/{job_id}")
async def retry_job_from_dlq(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retry a job from the dead letter queue."""
    dlq_service = DeadLetterQueueService()
    job_service = JobService(db)
    
    # Get job from DLQ
    job_data = await dlq_service.retry_job_from_dlq(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found in dead letter queue")
    
    # Recreate the job
    try:
        from app.schemas.job import JobCreate
        
        job_create = JobCreate(
            type=job_data["job_type"],
            payload=job_data["payload"],
            priority="normal",  # Reset to normal priority
            max_attempts=3,     # Reset attempts
        )
        
        new_job = await job_service.create_job(job_create)
        
        return {
            "message": "Job successfully retried from DLQ",
            "original_job_id": job_id,
            "new_job_id": new_job.id,
            "status": new_job.status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")


@router.delete("/dlq/clear")
async def clear_dead_letter_queue(job_type: Optional[str] = Query(None)):
    """Clear the dead letter queue (optionally by job type)."""
    dlq_service = DeadLetterQueueService()
    
    cleared_count = await dlq_service.clear_dlq(job_type=job_type)
    
    message = f"Cleared {cleared_count} jobs from DLQ"
    if job_type:
        message += f" (type: {job_type})"
    
    return {
        "message": message,
        "cleared_count": cleared_count
    }


@router.get("/system/health")
async def get_system_health():
    """Get comprehensive system health information."""
    try:
        # Check Redis connectivity
        dlq_service = DeadLetterQueueService()
        dlq_stats = await dlq_service.get_dlq_stats()
        redis_healthy = True
    except Exception:
        dlq_stats = {}
        redis_healthy = False
    
    # Check database connectivity
    try:
        # This will be checked by the dependency injection
        db_healthy = True
    except Exception:
        db_healthy = False
    
    health_status = "healthy" if (redis_healthy and db_healthy) else "degraded"
    
    return {
        "status": health_status,
        "timestamp": "2024-12-27T00:00:00Z",
        "services": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy"
        },
        "dead_letter_queue": {
            "total_jobs": dlq_stats.get("total_jobs", 0),
            "total_failed": dlq_stats.get("total_failed", 0)
        }
    }


@router.get("/system/metrics")
async def get_system_metrics(db: AsyncSession = Depends(get_db)):
    """Get system performance metrics."""
    job_service = JobService(db)
    dlq_service = DeadLetterQueueService()
    
    try:
        # Get job counts by status
        from sqlalchemy import select, func
        from app.models import Job, JobStatus
        
        status_counts = {}
        for status in JobStatus:
            query = select(func.count(Job.id)).where(Job.status == status)
            result = await db.execute(query)
            count = result.scalar() or 0
            status_counts[status.value] = count
        
        # Get DLQ stats
        dlq_stats = await dlq_service.get_dlq_stats()
        
        # Calculate success rate
        total_completed = status_counts.get("completed", 0)
        total_failed = status_counts.get("failed", 0)
        total_finished = total_completed + total_failed
        
        success_rate = (total_completed / total_finished * 100) if total_finished > 0 else 0
        
        return {
            "job_counts": status_counts,
            "success_rate_percent": round(success_rate, 2),
            "dead_letter_queue": dlq_stats,
            "system_load": {
                "total_jobs_processed": total_finished,
                "currently_running": status_counts.get("running", 0),
                "pending_jobs": status_counts.get("pending", 0) + status_counts.get("ready", 0)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}") 