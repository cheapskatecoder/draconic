import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set
from uuid import UUID
import traceback

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.services.job_service import JobService
from app.services.dependency_service import DependencyService
from app.services.websocket_manager import WebSocketManager
from app.services.resource_manager import ResourceManager
from app.services.redis_queue import RedisQueueService
from app.services.dead_letter_queue import DeadLetterQueueService
from app.workers.job_executor import JobExecutor
from app.models import JobStatus

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.resource_manager = ResourceManager(
            max_cpu=settings.max_cpu_units, max_memory=settings.max_memory_mb
        )
        self.redis_queue = RedisQueueService()
        self.dead_letter_queue = DeadLetterQueueService()
        self.job_executor = JobExecutor()
        self.running_jobs: Dict[UUID, asyncio.Task] = {}
        self.is_running = False
        self.shutdown_event = asyncio.Event()

    async def run(self):
        """Main scheduler loop."""
        self.is_running = True
        logger.info("Task scheduler started")

        # Initialize Redis resources
        await self.redis_queue.initialize_resources(
            settings.max_cpu_units, settings.max_memory_mb
        )

        try:
            while self.is_running:
                try:
                    await self._schedule_cycle()
                    await asyncio.sleep(1)  # Check every second
                except Exception as e:
                    logger.error(f"Error in scheduler cycle: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(5)  # Back off on error

        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        finally:
            await self._shutdown_cleanup()

    async def shutdown(self):
        """Gracefully shutdown the scheduler."""
        logger.info("Shutting down task scheduler...")
        self.is_running = False

        # Wait for current jobs to complete (with timeout)
        if self.running_jobs:
            logger.info(
                f"Waiting for {len(self.running_jobs)} running jobs to complete..."
            )
            await asyncio.wait_for(
                asyncio.gather(*self.running_jobs.values(), return_exceptions=True),
                timeout=30.0,  # 30 second timeout
            )

        self.shutdown_event.set()
        logger.info("Task scheduler shutdown complete")

    async def _schedule_cycle(self):
        """Single scheduling cycle."""
        async with AsyncSessionLocal() as db:
            job_service = JobService(db)

            # 1. Check and update blocked jobs
            await job_service.check_and_update_blocked_jobs()

            # 2. Clean up completed jobs
            await self._cleanup_completed_jobs()

            # 3. Handle retries for failed jobs
            await self._handle_retries(job_service)

            # 4. Schedule new jobs if resources are available
            await self._schedule_ready_jobs(job_service)

            # 5. Check for timed out jobs
            await self._check_timeouts(job_service)

    async def _schedule_ready_jobs(self, job_service: JobService):
        """Schedule ready jobs from Redis queues."""
        # Check if we're at max concurrent jobs
        if len(self.running_jobs) >= settings.max_concurrent_jobs:
            return

        # Try to pop a job from Redis (with resource allocation)
        job_data = await self.redis_queue.pop_job(timeout=1)
        if not job_data:
            return  # No jobs available or no resources

        # Get the job from database
        job_id = UUID(job_data["job_id"])
        job = await job_service.get_job(job_id)
        
        if not job or job.status != JobStatus.READY:
            # Job might have been cancelled or changed status
            # Release the allocated resources
            await self.redis_queue.release_resources(
                job_data["cpu_units"], job_data["memory_mb"]
            )
            return

        # Start the job (resources already allocated by Redis)
        await self._start_job_with_allocated_resources(job, job_service, job_data)

    async def _start_job_with_allocated_resources(self, job, job_service: JobService, job_data: dict):
        """Start executing a job with resources already allocated in Redis."""
        try:
            # Update job status to running
            await job_service.update_job_status(job.id, JobStatus.RUNNING)

            # Create execution task
            task = asyncio.create_task(self._execute_job_with_cleanup(job, job_data))

            self.running_jobs[job.id] = task

            # Broadcast job started event
            await self.websocket_manager.broadcast_job_update(
                job.id,
                "job_started",
                {
                    "job_id": str(job.id),
                    "type": job.type,
                    "priority": job.priority,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            logger.info(
                f"Started job {job.id} (type: {job.type}, priority: {job.priority})"
            )

        except Exception as e:
            logger.error(f"Error starting job {job.id}: {e}")
            # Release resources in Redis if job startup failed
            await self.redis_queue.release_resources(
                job_data["cpu_units"], job_data["memory_mb"]
            )

    async def _start_job(self, job, job_service: JobService):
        """Legacy method - kept for backward compatibility."""
        # This method is now unused but kept to avoid breaking existing code
        pass

    async def _execute_job_with_cleanup(self, job, job_data: dict):
        """Execute a job and handle cleanup."""
        try:
            # Execute the job
            result = await self.job_executor.execute_job(job)

            # Update job with result
            async with AsyncSessionLocal() as db:
                job_service = JobService(db)
                await job_service.update_job_status(
                    job.id, JobStatus.COMPLETED, result=result
                )

                # Mark job as completed in Redis for dependency tracking
                await self.redis_queue.mark_job_completed(job.id)

                # Log successful completion
                await job_service._add_log(
                    job.id, "info", "Job completed successfully", "scheduler"
                )

            # Broadcast completion
            await self.websocket_manager.broadcast_job_update(
                job.id,
                "job_completed",
                {
                    "job_id": str(job.id),
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            logger.info(f"Job {job.id} completed successfully")

        except asyncio.TimeoutError:
            # Handle timeout
            await self._handle_job_timeout(job, job_data)

        except Exception as e:
            # Handle job failure
            await self._handle_job_failure(job, str(e), traceback.format_exc(), job_data)

        finally:
            # Always cleanup
            await self._cleanup_job(job, job_data)

    async def _handle_job_failure(self, job, error_message: str, error_traceback: str, job_data: dict):
        """Handle job failure and retries."""
        logger.error(f"Job {job.id} failed: {error_message}")

        async with AsyncSessionLocal() as db:
            job_service = JobService(db)
            dependency_service = DependencyService(db)

            # Check if we should retry
            if job.current_attempt < job.max_attempts:
                # Schedule retry
                next_retry_delay = self._calculate_retry_delay(
                    job.current_attempt, job.backoff_multiplier
                )
                next_retry_at = datetime.utcnow() + timedelta(seconds=next_retry_delay)

                await job_service.update_job_status(
                    job.id,
                    JobStatus.PENDING,
                    current_attempt=job.current_attempt + 1,
                    next_retry_at=next_retry_at,
                    error_message=error_message,
                )

                # Log retry
                await job_service._add_log(
                    job.id,
                    "warning",
                    f"Job failed, will retry in {next_retry_delay} seconds (attempt {job.current_attempt + 1}/{job.max_attempts})",
                    "scheduler",
                )

                # Broadcast retry event
                await self.websocket_manager.broadcast_job_update(
                    job.id,
                    "job_retry_scheduled",
                    {
                        "job_id": str(job.id),
                        "attempt": job.current_attempt + 1,
                        "max_attempts": job.max_attempts,
                        "retry_at": next_retry_at.isoformat(),
                        "error": error_message,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            else:
                # Mark as permanently failed
                await job_service.update_job_status(
                    job.id, JobStatus.FAILED, error_message=error_message
                )

                # Add to dead letter queue
                await self.dead_letter_queue.add_to_dlq(
                    job.id, job.type, error_message, job.max_attempts, job.payload
                )

                # Mark job as completed in Redis for dependency tracking (even if failed)
                await self.redis_queue.mark_job_completed(job.id)

                # Log final failure
                await job_service._add_log(
                    job.id,
                    "error",
                    f"Job failed permanently after {job.max_attempts} attempts: {error_message}",
                    "scheduler",
                )

                # Mark dependent jobs as failed
                await dependency_service.mark_dependents_as_failed(job.id)

                # Broadcast failure event
                await self.websocket_manager.broadcast_job_update(
                    job.id,
                    "job_failed",
                    {
                        "job_id": str(job.id),
                        "error": error_message,
                        "final_attempt": True,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

    async def _handle_job_timeout(self, job, job_data: dict):
        """Handle job timeout."""
        logger.warning(f"Job {job.id} timed out")

        async with AsyncSessionLocal() as db:
            job_service = JobService(db)

            # Check if we should retry
            if job.current_attempt < job.max_attempts:
                # Schedule retry for timeout
                next_retry_delay = self._calculate_retry_delay(
                    job.current_attempt, job.backoff_multiplier
                )
                next_retry_at = datetime.utcnow() + timedelta(seconds=next_retry_delay)

                await job_service.update_job_status(
                    job.id,
                    JobStatus.PENDING,
                    current_attempt=job.current_attempt + 1,
                    next_retry_at=next_retry_at,
                    error_message="Job timed out",
                )

                await job_service._add_log(
                    job.id,
                    "warning",
                    f"Job timed out, will retry in {next_retry_delay} seconds",
                    "scheduler",
                )
            else:
                # Mark as timed out permanently
                await job_service.update_job_status(
                    job.id, JobStatus.TIMEOUT, error_message="Job timed out permanently"
                )

                await job_service._add_log(
                    job.id, "error", "Job timed out permanently", "scheduler"
                )

    async def _cleanup_job(self, job, job_data: dict):
        """Cleanup job resources and tracking."""
        # Release resources in Redis
        await self.redis_queue.release_resources(
            job_data["cpu_units"], job_data["memory_mb"]
        )

        # Remove from running jobs
        if job.id in self.running_jobs:
            del self.running_jobs[job.id]

    async def _cleanup_completed_jobs(self):
        """Remove completed job tasks from tracking."""
        completed_jobs = []

        for job_id, task in self.running_jobs.items():
            if task.done():
                completed_jobs.append(job_id)

        for job_id in completed_jobs:
            del self.running_jobs[job_id]

    async def _handle_retries(self, job_service: JobService):
        """Handle jobs that are ready for retry."""
        # This would typically be more sophisticated in production
        # For now, we'll just change status back to READY for jobs that are due for retry
        pass

    async def _check_timeouts(self, job_service: JobService):
        """Check for jobs that have exceeded their timeout."""
        # In a production system, you'd track job start times and check against timeout
        pass

    def _calculate_retry_delay(self, attempt: int, multiplier: float) -> int:
        """Calculate exponential backoff delay for retries."""
        base_delay = 10  # 10 seconds base
        return min(base_delay * (multiplier**attempt), 300)  # Max 5 minutes

    async def _shutdown_cleanup(self):
        """Cleanup during shutdown."""
        # Cancel all running jobs
        for job_id, task in self.running_jobs.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled job {job_id} during shutdown")

        # Clear running jobs
        self.running_jobs.clear()

        # Reset resource manager
        self.resource_manager.reset()
