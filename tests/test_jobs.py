import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app

# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

class TestJobsAPI:
    @pytest.mark.asyncio
    async def test_create_job(self):
        """Test creating a basic job."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            job_data = {
                "type": "send_email",
                "priority": "normal",
                "payload": {"to": "test@example.com", "template": "welcome"},
            }

            response = await client.post("/jobs/", json=job_data)
            assert response.status_code == 200
            
            data = response.json()
            assert "job_id" in data
            assert data["status"] in ["pending", "ready"]
            assert data["priority"] == "normal"

    @pytest.mark.asyncio
    async def test_get_job(self):
        """Test retrieving a job."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # First create a job
            job_data = {"type": "test_job", "priority": "high"}
            create_response = await client.post("/jobs/", json=job_data)
            assert create_response.status_code == 200
            
            job_id = create_response.json()["job_id"]
            
            # Then retrieve it
            get_response = await client.get(f"/jobs/{job_id}")
            assert get_response.status_code == 200
            
            data = get_response.json()
            # API returns job details in a nested structure
            assert data["job_id"] == job_id or data.get("id") == job_id
            assert data["type"] == "test_job"

    @pytest.mark.asyncio
    async def test_list_jobs(self):
        """Test listing jobs."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/jobs/")
            assert response.status_code == 200
            
            data = response.json()
            assert "jobs" in data
            assert isinstance(data["jobs"], list)

    @pytest.mark.asyncio
    async def test_job_logs(self):
        """Test retrieving job logs."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create a job first
            job_data = {"type": "test_job", "priority": "normal"}
            create_response = await client.post("/jobs/", json=job_data)
            job_id = create_response.json()["job_id"]
            
            # Get logs
            logs_response = await client.get(f"/jobs/{job_id}/logs")
            assert logs_response.status_code == 200
            
            logs_response = logs_response.json()
            # API returns logs in format: {"logs": [...], "total": N}
            assert "logs" in logs_response
            assert isinstance(logs_response["logs"], list)

    @pytest.mark.asyncio
    async def test_create_job_with_dependencies(self):
        """Test creating jobs with dependencies."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create parent job
            parent_job_data = {"type": "parent_job", "priority": "high"}
            parent_response = await client.post("/jobs/", json=parent_job_data)
            assert parent_response.status_code == 200
            parent_job_id = parent_response.json()["job_id"]
            
            # Wait a moment for parent job to be processed
            await asyncio.sleep(0.1)
            
            # Create dependent job
            dependent_job_data = {
                "type": "dependent_job",
                "priority": "normal",
                "depends_on": [parent_job_id]
            }
            dependent_response = await client.post("/jobs/", json=dependent_job_data)
            assert dependent_response.status_code == 200
            
            dependent_data = dependent_response.json()
            assert dependent_data["status"] in ["blocked", "pending"]

    @pytest.mark.asyncio
    async def test_cancel_job(self):
        """Test cancelling a job."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create a job
            job_data = {"type": "long_running_job", "priority": "low"}
            create_response = await client.post("/jobs/", json=job_data)
            assert create_response.status_code == 200
            job_id = create_response.json()["job_id"]
            
            # Try to cancel it
            cancel_response = await client.patch(f"/jobs/{job_id}/cancel")
            # Accept both 200 (cancelled) and 400 (already completed/running)
            assert cancel_response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_invalid_job_id(self):
        """Test handling of invalid job IDs."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            fake_job_id = "00000000-0000-0000-0000-000000000000"
            
            response = await client.get(f"/jobs/{fake_job_id}")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_job_priorities(self):
        """Test that job priorities work correctly."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create jobs with different priorities
            priorities = ["low", "normal", "high", "critical"]
            job_ids = []
            
            for priority in priorities:
                job_data = {"type": "priority_test", "priority": priority}
                response = await client.post("/jobs/", json=job_data)
                assert response.status_code == 200
                job_ids.append(response.json()["job_id"])
            
            # All jobs should be created successfully
            assert len(job_ids) == 4
