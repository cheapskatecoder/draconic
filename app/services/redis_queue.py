import json
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
import redis.asyncio as redis
from app.core.config import settings
from app.models import JobPriority

logger = logging.getLogger(__name__)


class RedisQueueService:
    def __init__(self):
        self.redis = redis.from_url(
            settings.redis_url,
            encoding="utf-8", 
            decode_responses=True
        )
        
        # Queue names by priority
        self.queues = {
            JobPriority.CRITICAL: "queue:critical",
            JobPriority.HIGH: "queue:high", 
            JobPriority.NORMAL: "queue:normal",
            JobPriority.LOW: "queue:low"
        }
        
        # Resource tracking keys
        self.resource_keys = {
            "cpu": "resources:cpu",
            "memory": "resources:memory",
            "max_cpu": "resources:max_cpu",
            "max_memory": "resources:max_memory"
        }
        
        # Job claiming key
        self.claiming_key = "jobs:claiming"

    async def initialize_resources(self, max_cpu: int, max_memory: int):
        """Initialize resource limits in Redis."""
        async with self.redis.pipeline() as pipe:
            pipe.set(self.resource_keys["max_cpu"], max_cpu)
            pipe.set(self.resource_keys["max_memory"], max_memory)
            pipe.set(self.resource_keys["cpu"], 0)  # allocated CPU
            pipe.set(self.resource_keys["memory"], 0)  # allocated memory
            await pipe.execute()
        
        logger.info(f"Initialized Redis resources: {max_cpu} CPU, {max_memory}MB memory")

    async def push_job(self, job_id: UUID, priority: JobPriority, cpu_units: int, memory_mb: int) -> bool:
        """Push job to appropriate priority queue."""
        queue_name = self.queues[priority]
        
        job_data = {
            "job_id": str(job_id),
            "cpu_units": cpu_units,
            "memory_mb": memory_mb,
            "priority": priority.value
        }
        
        # Push to queue
        await self.redis.lpush(queue_name, json.dumps(job_data))
        logger.info(f"Pushed job {job_id} to {queue_name}")
        return True

    async def pop_job(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Pop job from highest priority queue with available resources.
        
        Uses BLPOP to block until job available, then atomic resource allocation.
        """
        # Check queues in priority order
        queue_names = [
            self.queues[JobPriority.CRITICAL],
            self.queues[JobPriority.HIGH], 
            self.queues[JobPriority.NORMAL],
            self.queues[JobPriority.LOW]
        ]
        
        # Block until job available in any queue
        result = await self.redis.blpop(queue_names, timeout=timeout)
        if not result:
            return None
            
        queue_name, job_data_str = result
        job_data = json.loads(job_data_str)
        
        # Try to allocate resources atomically
        if await self._allocate_resources(job_data["cpu_units"], job_data["memory_mb"]):
            logger.info(f"Popped job {job_data['job_id']} from {queue_name}")
            return job_data
        else:
            # Put job back if no resources available
            await self.redis.lpush(queue_name, job_data_str)
            logger.warning(f"Insufficient resources for job {job_data['job_id']}, returned to queue")
            return None

    async def _allocate_resources(self, cpu_units: int, memory_mb: int) -> bool:
        """Atomically allocate resources using Redis transaction."""
        async with self.redis.pipeline() as pipe:
            while True:
                try:
                    # Watch resource keys for changes
                    pipe.watch(self.resource_keys["cpu"], self.resource_keys["memory"])
                    
                    # Get current allocation
                    current_cpu = int(await self.redis.get(self.resource_keys["cpu"]) or 0)
                    current_memory = int(await self.redis.get(self.resource_keys["memory"]) or 0)
                    max_cpu = int(await self.redis.get(self.resource_keys["max_cpu"]) or 0)
                    max_memory = int(await self.redis.get(self.resource_keys["max_memory"]) or 0)
                    
                    # Check if resources available
                    if (current_cpu + cpu_units > max_cpu or 
                        current_memory + memory_mb > max_memory):
                        pipe.unwatch()
                        return False
                    
                    # Allocate resources atomically
                    pipe.multi()
                    pipe.set(self.resource_keys["cpu"], current_cpu + cpu_units)
                    pipe.set(self.resource_keys["memory"], current_memory + memory_mb)
                    await pipe.execute()
                    
                    logger.debug(f"Allocated {cpu_units} CPU, {memory_mb}MB memory")
                    return True
                    
                except redis.WatchError:
                    # Retry if watched keys changed
                    continue

    async def release_resources(self, cpu_units: int, memory_mb: int):
        """Release allocated resources."""
        async with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(self.resource_keys["cpu"], self.resource_keys["memory"])
                    
                    current_cpu = int(await self.redis.get(self.resource_keys["cpu"]) or 0)
                    current_memory = int(await self.redis.get(self.resource_keys["memory"]) or 0)
                    
                    pipe.multi()
                    pipe.set(self.resource_keys["cpu"], max(0, current_cpu - cpu_units))
                    pipe.set(self.resource_keys["memory"], max(0, current_memory - memory_mb))
                    await pipe.execute()
                    
                    logger.debug(f"Released {cpu_units} CPU, {memory_mb}MB memory")
                    break
                    
                except redis.WatchError:
                    continue

    async def get_resource_usage(self) -> Dict[str, int]:
        """Get current resource usage."""
        async with self.redis.pipeline() as pipe:
            pipe.get(self.resource_keys["cpu"])
            pipe.get(self.resource_keys["memory"])
            pipe.get(self.resource_keys["max_cpu"])
            pipe.get(self.resource_keys["max_memory"])
            results = await pipe.execute()
        
        return {
            "allocated_cpu": int(results[0] or 0),
            "allocated_memory": int(results[1] or 0),
            "max_cpu": int(results[2] or 0),
            "max_memory": int(results[3] or 0)
        }

    async def get_queue_sizes(self) -> Dict[str, int]:
        """Get sizes of all priority queues."""
        async with self.redis.pipeline() as pipe:
            for queue_name in self.queues.values():
                pipe.llen(queue_name)
            results = await pipe.execute()
        
        return {
            priority.value: size 
            for priority, size in zip(self.queues.keys(), results)
        }

    async def clear_all_queues(self):
        """Clear all job queues (for testing/cleanup)."""
        async with self.redis.pipeline() as pipe:
            for queue_name in self.queues.values():
                pipe.delete(queue_name)
            await pipe.execute()
        
        logger.info("Cleared all Redis job queues")

    async def push_retry_job(self, job_id: UUID, priority: JobPriority, 
                           cpu_units: int, memory_mb: int, delay_seconds: int):
        """Push job to retry queue with delay."""
        # For simplicity, we'll use immediate push for now
        # In production, you might use Redis delayed queues or external scheduler
        await self.push_job(job_id, priority, cpu_units, memory_mb)

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()

    async def get_recently_completed_jobs(self) -> List[str]:
        """Get list of recently completed job IDs and clear the list."""
        key = "task_queue:recently_completed"
        
        # Get all completed job IDs and clear the list atomically
        pipe = self.redis.pipeline()
        pipe.lrange(key, 0, -1)  # Get all items
        pipe.delete(key)  # Clear the list
        results = await pipe.execute()
        
        return results[0] if results[0] else []
    
    async def mark_job_completed(self, job_id: UUID):
        """Mark a job as recently completed for dependency checking."""
        key = "task_queue:recently_completed"
        
        # Add to list with expiration (keep for 60 seconds)
        await self.redis.lpush(key, str(job_id))
        await self.redis.expire(key, 60) 