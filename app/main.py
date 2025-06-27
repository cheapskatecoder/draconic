from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
import asyncio
from contextlib import asynccontextmanager

from app.core.database import get_db, engine, Base
from app.core.config import settings
from app.routes import jobs
from app.services.websocket_manager import WebSocketManager
from app.services.scheduler import TaskScheduler

# Setup logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Global instances
websocket_manager = WebSocketManager()
task_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Task Queue System...")

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start the task scheduler
    global task_scheduler
    task_scheduler = TaskScheduler(websocket_manager)
    asyncio.create_task(task_scheduler.run())

    logger.info("Task Queue System started successfully!")

    yield

    # Shutdown
    logger.info("Shutting down Task Queue System...")
    if task_scheduler:
        await task_scheduler.shutdown()
    logger.info("Task Queue System shutdown complete.")


app = FastAPI(
    title="Task Queue System",
    description="Production-ready task queue system with job scheduling, prioritization, and execution",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/")
async def root():
    return {"message": "Task Queue System API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.websocket("/jobs/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
