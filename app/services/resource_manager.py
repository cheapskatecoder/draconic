import threading
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ResourceManager:
    def __init__(self, max_cpu: int, max_memory: int):
        self.max_cpu = max_cpu
        self.max_memory = max_memory
        self.allocated_cpu = 0
        self.allocated_memory = 0
        self._lock = threading.Lock()

    def can_allocate(self, cpu_units: int, memory_mb: int) -> bool:
        """Check if resources can be allocated."""
        with self._lock:
            return (
                self.allocated_cpu + cpu_units <= self.max_cpu
                and self.allocated_memory + memory_mb <= self.max_memory
            )

    def allocate(self, cpu_units: int, memory_mb: int) -> bool:
        """Allocate resources if available."""
        with self._lock:
            if self.can_allocate(cpu_units, memory_mb):
                self.allocated_cpu += cpu_units
                self.allocated_memory += memory_mb
                logger.debug(
                    f"Allocated {cpu_units} CPU, {memory_mb}MB memory. Total: {self.allocated_cpu}/{self.max_cpu} CPU, {self.allocated_memory}/{self.max_memory}MB memory"
                )
                return True
            return False

    def release(self, cpu_units: int, memory_mb: int):
        """Release allocated resources."""
        with self._lock:
            self.allocated_cpu = max(0, self.allocated_cpu - cpu_units)
            self.allocated_memory = max(0, self.allocated_memory - memory_mb)
            logger.debug(
                f"Released {cpu_units} CPU, {memory_mb}MB memory. Total: {self.allocated_cpu}/{self.max_cpu} CPU, {self.allocated_memory}/{self.max_memory}MB memory"
            )

    def get_available_resources(self) -> Tuple[int, int]:
        """Get available CPU and memory."""
        with self._lock:
            return (
                self.max_cpu - self.allocated_cpu,
                self.max_memory - self.allocated_memory,
            )

    def get_utilization(self) -> Tuple[float, float]:
        """Get resource utilization as percentages."""
        with self._lock:
            cpu_util = (
                (self.allocated_cpu / self.max_cpu) * 100 if self.max_cpu > 0 else 0
            )
            memory_util = (
                (self.allocated_memory / self.max_memory) * 100
                if self.max_memory > 0
                else 0
            )
            return cpu_util, memory_util

    def reset(self):
        """Reset all resource allocations."""
        with self._lock:
            self.allocated_cpu = 0
            self.allocated_memory = 0
            logger.info("Resource manager reset")
