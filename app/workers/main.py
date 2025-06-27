import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.services.websocket_manager import WebSocketManager
from app.services.scheduler import TaskScheduler

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class WorkerManager:
    def __init__(self):
        self.websocket_manager = WebSocketManager()
        self.scheduler = None
        self.is_running = False

    async def start(self):
        """Start the worker."""
        logger.info("Starting worker process...")

        # Create database tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Start scheduler
        self.scheduler = TaskScheduler(self.websocket_manager)
        self.is_running = True

        # Run scheduler
        await self.scheduler.run()

    async def shutdown(self):
        """Shutdown the worker gracefully."""
        logger.info("Shutting down worker...")
        self.is_running = False

        if self.scheduler:
            await self.scheduler.shutdown()

        logger.info("Worker shutdown complete")


async def main():
    worker_manager = WorkerManager()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(worker_manager.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker_manager.start()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)
    finally:
        await worker_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
