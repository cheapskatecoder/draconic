import asyncio
import json
import logging
from typing import Dict, Any
from datetime import datetime
import traceback

from app.models import Job

logger = logging.getLogger(__name__)


class JobExecutor:
    """Executes different types of jobs."""

    def __init__(self):
        self.job_handlers = {
            "send_email": self._handle_send_email,
            "data_export": self._handle_data_export,
            "data_fetch": self._handle_data_fetch,
            "data_processing": self._handle_data_processing,
            "report_generation": self._handle_report_generation,
            "generate_report": self._handle_report_generation,  # alias
        }

    async def execute_job(self, job: Job) -> Dict[str, Any]:
        """Execute a job based on its type."""
        logger.info(f"Executing job {job.id} of type {job.type}")

        start_time = datetime.utcnow()

        try:
            # Get the appropriate handler
            handler = self.job_handlers.get(job.type, self._handle_generic_job)

            # Execute with timeout
            result = await asyncio.wait_for(handler(job), timeout=job.timeout_seconds)

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            return {
                "status": "completed",
                "result": result,
                "duration_seconds": duration,
                "completed_at": end_time.isoformat(),
            }

        except asyncio.TimeoutError:
            logger.error(f"Job {job.id} timed out after {job.timeout_seconds} seconds")
            raise
        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _handle_send_email(self, job: Job) -> Dict[str, Any]:
        """Handle email sending job."""
        payload = job.payload

        # Simulate email sending
        await asyncio.sleep(2)  # Simulate email API call

        return {
            "email_sent": True,
            "recipient": payload.get("to", "unknown"),
            "template": payload.get("template", "default"),
            "message_id": f"msg_{job.id}_{datetime.utcnow().timestamp()}",
        }

    async def _handle_data_export(self, job: Job) -> Dict[str, Any]:
        """Handle data export job."""
        payload = job.payload

        # Simulate data export process
        user_id = payload.get("user_id")
        export_format = payload.get("format", "csv")

        # Simulate export time based on format
        if export_format == "pdf":
            await asyncio.sleep(8)  # PDF takes longer
        elif export_format == "excel":
            await asyncio.sleep(5)
        else:  # CSV
            await asyncio.sleep(3)

        # Simulate some data processing
        records_exported = 1000 + (
            hash(str(job.id)) % 5000
        )  # Simulate variable record count

        return {
            "export_completed": True,
            "user_id": user_id,
            "format": export_format,
            "records_exported": records_exported,
            "file_size_mb": records_exported * 0.001,  # Simulate file size
            "download_url": f"/exports/{job.id}.{export_format}",
        }

    async def _handle_data_fetch(self, job: Job) -> Dict[str, Any]:
        """Handle data fetching job."""
        payload = job.payload

        source = payload.get("source", "unknown")
        symbols = payload.get("symbols", [])

        # Simulate API calls
        await asyncio.sleep(3)

        # Simulate fetched data
        data = {}
        for symbol in symbols:
            data[symbol] = {
                "price": 100 + (hash(symbol) % 500),  # Simulate price
                "volume": 1000000 + (hash(symbol) % 10000000),  # Simulate volume
                "timestamp": datetime.utcnow().isoformat(),
            }

        return {
            "fetch_completed": True,
            "source": source,
            "symbols_fetched": len(symbols),
            "data": data,
        }

    async def _handle_data_processing(self, job: Job) -> Dict[str, Any]:
        """Handle data processing job."""
        payload = job.payload

        # Simulate intensive data processing
        await asyncio.sleep(6)  # Processing takes time

        return {
            "processing_completed": True,
            "records_processed": 10000,
            "processing_time_seconds": 6,
            "output_file": f"/processed/{job.id}_processed.json",
        }

    async def _handle_report_generation(self, job: Job) -> Dict[str, Any]:
        """Handle report generation job."""
        payload = job.payload

        report_type = payload.get("report_type", "unknown")
        date = payload.get("date", datetime.utcnow().strftime("%Y-%m-%d"))

        # Simulate report generation time based on type
        if report_type == "daily_summary":
            await asyncio.sleep(4)
        elif report_type == "weekly_analysis":
            await asyncio.sleep(8)
        elif report_type == "monthly_report":
            await asyncio.sleep(12)
        else:
            await asyncio.sleep(5)

        return {
            "report_generated": True,
            "report_type": report_type,
            "report_date": date,
            "pages": 15 + (hash(str(job.id)) % 50),  # Simulate variable page count
            "charts_generated": 5 + (hash(str(job.id)) % 10),
            "report_url": f"/reports/{job.id}_{report_type}_{date}.pdf",
        }

    async def _handle_generic_job(self, job: Job) -> Dict[str, Any]:
        """Handle generic/unknown job types."""
        logger.warning(
            f"No specific handler for job type '{job.type}', using generic handler"
        )

        # Simulate some work
        await asyncio.sleep(2)

        return {
            "generic_job_completed": True,
            "job_type": job.type,
            "payload_processed": True,
            "note": f"Generic handler executed for {job.type}",
        }
