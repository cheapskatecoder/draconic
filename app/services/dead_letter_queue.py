import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeadLetterQueueService:
    """Dead Letter Queue for permanently failed jobs."""
    
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url)
        self.dlq_key = "task_queue:dead_letter"
        self.dlq_stats_key = "task_queue:dlq_stats"
    
    async def add_to_dlq(self, job_id: UUID, job_type: str, error_message: str, 
                        attempts: int, payload: Dict[str, Any]) -> bool:
        """Add a permanently failed job to the dead letter queue."""
        try:
            dlq_entry = {
                "job_id": str(job_id),
                "job_type": job_type,
                "error_message": error_message,
                "attempts": attempts,
                "payload": payload,
                "failed_at": datetime.utcnow().isoformat(),
                "added_to_dlq_at": datetime.utcnow().isoformat()
            }
            
            # Add to dead letter queue
            await self.redis.lpush(self.dlq_key, json.dumps(dlq_entry))
            
            # Update stats
            await self._update_dlq_stats(job_type)
            
            logger.warning(f"Job {job_id} added to dead letter queue: {error_message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id} to DLQ: {e}")
            return False
    
    async def get_dlq_jobs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get jobs from the dead letter queue."""
        try:
            # Get jobs from Redis list
            jobs_data = await self.redis.lrange(
                self.dlq_key, offset, offset + limit - 1
            )
            
            jobs = []
            for job_data in jobs_data:
                try:
                    job = json.loads(job_data)
                    jobs.append(job)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in DLQ: {job_data}")
                    continue
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to get DLQ jobs: {e}")
            return []
    
    async def get_dlq_count(self) -> int:
        """Get total number of jobs in dead letter queue."""
        try:
            return await self.redis.llen(self.dlq_key)
        except Exception as e:
            logger.error(f"Failed to get DLQ count: {e}")
            return 0
    
    async def get_dlq_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics."""
        try:
            stats_data = await self.redis.hgetall(self.dlq_stats_key)
            
            # Convert bytes to strings and parse
            stats = {}
            for key, value in stats_data.items():
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                value_str = value.decode('utf-8') if isinstance(value, bytes) else value
                
                try:
                    stats[key_str] = int(value_str)
                except ValueError:
                    stats[key_str] = value_str
            
            # Add total count
            stats["total_jobs"] = await self.get_dlq_count()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get DLQ stats: {e}")
            return {"total_jobs": 0}
    
    async def retry_job_from_dlq(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Remove a job from DLQ for retry (returns job data)."""
        try:
            # Get all jobs and find the one to retry
            jobs_data = await self.redis.lrange(self.dlq_key, 0, -1)
            
            for i, job_data in enumerate(jobs_data):
                try:
                    job = json.loads(job_data)
                    if job["job_id"] == str(job_id):
                        # Remove from DLQ
                        await self.redis.lrem(self.dlq_key, 1, job_data)
                        logger.info(f"Job {job_id} removed from DLQ for retry")
                        return job
                except json.JSONDecodeError:
                    continue
            
            logger.warning(f"Job {job_id} not found in DLQ")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retry job {job_id} from DLQ: {e}")
            return None
    
    async def clear_dlq(self, job_type: Optional[str] = None) -> int:
        """Clear dead letter queue (optionally by job type)."""
        try:
            if job_type is None:
                # Clear all jobs
                count = await self.redis.llen(self.dlq_key)
                await self.redis.delete(self.dlq_key)
                await self.redis.delete(self.dlq_stats_key)
                logger.info(f"Cleared {count} jobs from DLQ")
                return count
            else:
                # Clear jobs of specific type
                jobs_data = await self.redis.lrange(self.dlq_key, 0, -1)
                removed_count = 0
                
                for job_data in jobs_data:
                    try:
                        job = json.loads(job_data)
                        if job.get("job_type") == job_type:
                            await self.redis.lrem(self.dlq_key, 1, job_data)
                            removed_count += 1
                    except json.JSONDecodeError:
                        continue
                
                logger.info(f"Cleared {removed_count} jobs of type '{job_type}' from DLQ")
                return removed_count
                
        except Exception as e:
            logger.error(f"Failed to clear DLQ: {e}")
            return 0
    
    async def _update_dlq_stats(self, job_type: str):
        """Update DLQ statistics."""
        try:
            # Increment total count
            await self.redis.hincrby(self.dlq_stats_key, "total_failed", 1)
            
            # Increment count by job type
            await self.redis.hincrby(self.dlq_stats_key, f"failed_{job_type}", 1)
            
            # Update last failure timestamp
            await self.redis.hset(
                self.dlq_stats_key, 
                "last_failure", 
                datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to update DLQ stats: {e}")
    
    async def get_recent_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent failures from DLQ."""
        try:
            # Get recent jobs (LPUSH adds to head, so head = most recent)
            jobs_data = await self.redis.lrange(self.dlq_key, 0, limit - 1)
            
            jobs = []
            for job_data in jobs_data:
                try:
                    job = json.loads(job_data)
                    jobs.append(job)
                except json.JSONDecodeError:
                    continue
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to get recent failures: {e}")
            return [] 