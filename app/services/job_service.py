from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update, case
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import logging

from app.models import Job, JobStatus, JobPriority, JobDependency, JobExecution, JobLog
from app.schemas import JobCreate
from app.services.dependency_service import DependencyService
from app.services.redis_queue import RedisQueueService

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, db: AsyncSession, redis_queue: Optional[RedisQueueService] = None):
        self.db = db
        self.dependency_service = DependencyService(db)
        # Only initialize Redis if not provided and not in test environment
        if redis_queue is not None:
            self.redis_queue = redis_queue
        else:
            try:
                self.redis_queue = RedisQueueService()
            except Exception:
                # In test environment or when Redis is unavailable, use None
                self.redis_queue = None

    async def create_job(self, job_data: JobCreate) -> Job:
        """Create a new job with dependencies."""

        # Check for idempotency
        if job_data.idempotency_key:
            existing_job = await self._get_job_by_idempotency_key(
                job_data.idempotency_key
            )
            if existing_job:
                return existing_job

        # Create the job
        job = Job(
            id=uuid4(),
            type=job_data.type,
            priority=job_data.priority,
            payload=job_data.payload,
            cpu_units=job_data.resource_requirements.cpu_units,
            memory_mb=job_data.resource_requirements.memory_mb,
            timeout_seconds=job_data.timeout_seconds,
            max_attempts=job_data.retry_config.max_attempts,
            backoff_multiplier=job_data.retry_config.backoff_multiplier,
            idempotency_key=job_data.idempotency_key,
        )

        self.db.add(job)
        await self.db.flush()  # Get the job ID

        # Add dependencies if provided
        if job_data.depends_on:
            await self.dependency_service.add_dependencies(job.id, job_data.depends_on)

            # Check for circular dependencies
            if await self.dependency_service.has_circular_dependency(job.id):
                raise ValueError("Circular dependency detected")

            # Set job status to BLOCKED initially
            job.status = JobStatus.BLOCKED
        else:
            # No dependencies, job is ready to run
            job.status = JobStatus.READY

        await self.db.commit()
        await self.db.refresh(job)

        # Push to Redis queue if job is ready and Redis is available
        if job.status == JobStatus.READY and self.redis_queue:
            await self.redis_queue.push_job(
                job.id, job.priority, job.cpu_units, job.memory_mb
            )

        # Log job creation
        await self._add_log(
            job.id,
            "info",
            f"Job created with type '{job.type}' and priority '{job.priority}'",
        )

        return job

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        """Get a job by ID with all relationships loaded."""
        query = (
            select(Job)
            .options(
                selectinload(Job.dependencies),
                selectinload(Job.dependents),
                selectinload(Job.executions),
            )
            .where(Job.id == job_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[JobStatus] = None,
        priority: Optional[JobPriority] = None,
        job_type: Optional[str] = None,
    ) -> Tuple[List[Job], int]:
        """List jobs with filtering and pagination."""

        # Build base query
        query = select(Job)
        count_query = select(func.count(Job.id))

        # Apply filters
        conditions = []
        if status:
            conditions.append(Job.status == status)
        if priority:
            conditions.append(Job.priority == priority)
        if job_type:
            conditions.append(Job.type.ilike(f"%{job_type}%"))

        if conditions:
            filter_condition = and_(*conditions)
            query = query.where(filter_condition)
            count_query = count_query.where(filter_condition)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and ordering
        query = (
            query.order_by(Job.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        # Execute query
        result = await self.db.execute(query)
        jobs = result.scalars().all()

        return jobs, total

    async def cancel_job(self, job_id: UUID) -> bool:
        """Cancel a job if it's in a cancellable state."""
        job = await self.get_job(job_id)
        if not job:
            return False

        # Check if job can be cancelled
        if job.status not in [JobStatus.PENDING, JobStatus.READY, JobStatus.BLOCKED]:
            return False

        # Update job status
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()

        await self.db.commit()

        # Log cancellation
        await self._add_log(job_id, "info", "Job cancelled by user request")

        return True

    async def get_queue_position(self, job_id: UUID) -> Optional[int]:
        """Get the position of a job in the queue."""
        job = await self.get_job(job_id)
        if not job or job.status not in [
            JobStatus.PENDING,
            JobStatus.READY,
            JobStatus.BLOCKED,
        ]:
            return None

        # Count jobs with higher priority or same priority but created earlier
        priority_values = {
            JobPriority.CRITICAL: 4,
            JobPriority.HIGH: 3,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 1,
        }

        current_priority_value = priority_values[job.priority]

        query = select(func.count(Job.id)).where(
            and_(
                Job.status.in_([JobStatus.PENDING, JobStatus.READY]),
                or_(
                    # Higher priority jobs
                    Job.priority.in_(
                        [
                            p
                            for p, v in priority_values.items()
                            if v > current_priority_value
                        ]
                    ),
                    # Same priority but created earlier
                    and_(Job.priority == job.priority, Job.created_at < job.created_at),
                ),
            )
        )

        result = await self.db.execute(query)
        position = result.scalar() + 1  # 1-based position

        return position

    async def update_job_status(
        self, job_id: UUID, status: JobStatus, **kwargs
    ) -> bool:
        """Update job status and related fields."""
        update_data = {"status": status, "updated_at": datetime.utcnow()}

        # Add timestamp fields based on status
        if status == JobStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow()
        elif status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMEOUT,
        ]:
            update_data["completed_at"] = datetime.utcnow()

        # Add any additional fields
        update_data.update(kwargs)

        query = update(Job).where(Job.id == job_id).values(**update_data)
        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    async def get_ready_jobs(self, limit: int = 10) -> List[Job]:
        """Get jobs that are ready to be executed."""
        # Priority order: CRITICAL > HIGH > NORMAL > LOW
        # Within same priority: FIFO (created_at ASC)
        # Use CASE for SQLite compatibility instead of array_position
        priority_order_case = case(
            (Job.priority == JobPriority.CRITICAL, 1),
            (Job.priority == JobPriority.HIGH, 2),
            (Job.priority == JobPriority.NORMAL, 3),
            (Job.priority == JobPriority.LOW, 4),
            else_=5,
        )

        query = (
            select(Job)
            .where(Job.status == JobStatus.READY)
            .order_by(priority_order_case, Job.created_at.asc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def check_and_update_blocked_jobs(self):
        """Check blocked jobs and mark them as ready if dependencies are met.
        
        Optimized version that only checks blocked jobs that might be affected
        by recently completed jobs, avoiding full table scans.
        """
        if not self.redis_queue:
            # Fallback to old method if Redis not available
            return await self._check_blocked_jobs_fallback()
        
        # Get recently completed job IDs from Redis
        recently_completed = await self.redis_queue.get_recently_completed_jobs()
        
        if not recently_completed:
            return  # No recent completions, no need to check
        
        # Only check blocked jobs that depend on recently completed jobs
        for completed_job_id in recently_completed:
            await self._check_dependents_of_completed_job(UUID(completed_job_id))
    
    async def _check_blocked_jobs_fallback(self):
        """Fallback method for checking blocked jobs without Redis optimization."""
        # Get all blocked jobs (old inefficient method)
        blocked_jobs_query = select(Job).where(Job.status == JobStatus.BLOCKED)
        result = await self.db.execute(blocked_jobs_query)
        blocked_jobs = result.scalars().all()

        for job in blocked_jobs:
            if await self.dependency_service.are_dependencies_satisfied(job.id):
                await self.update_job_status(job.id, JobStatus.READY)
                
                # Push to Redis queue now that it's ready
                if self.redis_queue:
                    await self.redis_queue.push_job(
                        job.id, job.priority, job.cpu_units, job.memory_mb
                    )
                
                await self._add_log(
                    job.id, "info", "Job unblocked - all dependencies satisfied"
                )
    
    async def _check_dependents_of_completed_job(self, completed_job_id: UUID):
        """Check and update blocked jobs that depend on a specific completed job."""
        # Get blocked jobs that depend on this completed job
        query = (
            select(Job)
            .join(JobDependency, Job.id == JobDependency.child_job_id)
            .where(
                and_(
                    Job.status == JobStatus.BLOCKED,
                    JobDependency.parent_job_id == completed_job_id
                )
            )
        )
        
        result = await self.db.execute(query)
        dependent_jobs = result.scalars().all()
        
        # Check each dependent job
        for job in dependent_jobs:
            if await self.dependency_service.are_dependencies_satisfied(job.id):
                await self.update_job_status(job.id, JobStatus.READY)
                
                # Push to Redis queue now that it's ready
                if self.redis_queue:
                    await self.redis_queue.push_job(
                        job.id, job.priority, job.cpu_units, job.memory_mb
                    )
                
                await self._add_log(
                    job.id, "info", "Job unblocked - all dependencies satisfied"
                )

    async def _get_job_by_idempotency_key(self, key: str) -> Optional[Job]:
        """Get job by idempotency key."""
        query = select(Job).where(Job.idempotency_key == key)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _add_log(
        self, job_id: UUID, level: str, message: str, context: str = "job_service"
    ):
        """Add a log entry for a job."""
        log = JobLog(job_id=job_id, level=level, message=message, context=context)
        self.db.add(log)
        await self.db.commit()
