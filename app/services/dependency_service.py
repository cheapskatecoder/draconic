from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Set
from uuid import UUID
import logging

from app.models import Job, JobStatus, JobDependency

logger = logging.getLogger(__name__)


class DependencyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_dependencies(self, job_id: UUID, dependency_ids: List[str]):
        """Add dependencies for a job."""
        for dep_id_str in dependency_ids:
            try:
                dep_id = UUID(dep_id_str)
                dependency = JobDependency(parent_job_id=dep_id, child_job_id=job_id)
                self.db.add(dependency)
            except ValueError:
                raise ValueError(f"Invalid job ID format: {dep_id_str}")

        await self.db.commit()

    async def job_exists(self, job_id_str: str) -> bool:
        """Check if a job exists."""
        try:
            job_id = UUID(job_id_str)
            query = select(Job.id).where(Job.id == job_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none() is not None
        except ValueError:
            return False

    async def has_circular_dependency(self, job_id: UUID) -> bool:
        """Check if adding this job would create a circular dependency."""
        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()

        return await self._has_cycle_dfs(job_id, visited, rec_stack)

    async def _has_cycle_dfs(
        self, job_id: UUID, visited: Set[UUID], rec_stack: Set[UUID]
    ) -> bool:
        """DFS helper for cycle detection."""
        visited.add(job_id)
        rec_stack.add(job_id)

        # Get all jobs that depend on this job (children)
        query = select(JobDependency.child_job_id).where(
            JobDependency.parent_job_id == job_id
        )
        result = await self.db.execute(query)
        children = result.scalars().all()

        for child_id in children:
            if child_id not in visited:
                if await self._has_cycle_dfs(child_id, visited, rec_stack):
                    return True
            elif child_id in rec_stack:
                return True

        rec_stack.remove(job_id)
        return False

    async def are_dependencies_satisfied(self, job_id: UUID) -> bool:
        """Check if all dependencies for a job are satisfied (completed)."""
        # Get all parent dependencies
        query = (
            select(Job.status)
            .join(JobDependency, Job.id == JobDependency.parent_job_id)
            .where(JobDependency.child_job_id == job_id)
        )

        result = await self.db.execute(query)
        dependency_statuses = result.scalars().all()

        # If no dependencies, they're satisfied
        if not dependency_statuses:
            return True

        # All dependencies must be completed
        return all(status == JobStatus.COMPLETED for status in dependency_statuses)

    async def get_dependency_chain(self, job_id: UUID) -> List[UUID]:
        """Get the full dependency chain for a job (topological order)."""
        # This is a simplified version - in production you might want a more sophisticated approach
        visited = set()
        result = []

        await self._build_dependency_chain(job_id, visited, result)

        return result

    async def _build_dependency_chain(
        self, job_id: UUID, visited: Set[UUID], result: List[UUID]
    ):
        """Recursively build dependency chain."""
        if job_id in visited:
            return

        visited.add(job_id)

        # Get all parent dependencies
        query = select(JobDependency.parent_job_id).where(
            JobDependency.child_job_id == job_id
        )
        db_result = await self.db.execute(query)
        parents = db_result.scalars().all()

        # Process parents first (dependencies)
        for parent_id in parents:
            await self._build_dependency_chain(parent_id, visited, result)

        # Add current job to result
        result.append(job_id)

    async def mark_dependents_as_failed(self, job_id: UUID):
        """Mark all dependent jobs as failed when a dependency fails."""
        # Get all jobs that depend on this job
        query = select(JobDependency.child_job_id).where(
            JobDependency.parent_job_id == job_id
        )

        result = await self.db.execute(query)
        dependent_job_ids = result.scalars().all()

        # Recursively mark dependents as failed
        for dependent_id in dependent_job_ids:
            # Update job status to failed
            from app.services.job_service import JobService

            job_service = JobService(self.db)
            await job_service.update_job_status(
                dependent_id, JobStatus.FAILED, error_message="Dependency job failed"
            )

            # Log the failure
            await job_service._add_log(
                dependent_id,
                "error",
                f"Job failed due to dependency job {job_id} failure",
                "dependency_service",
            )

            # Recursively mark their dependents as failed too
            await self.mark_dependents_as_failed(dependent_id)
