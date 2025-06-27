import asyncio
import time
import pytest
import psutil
from httpx import AsyncClient
from app.main import app


class TestPerformance:
    """Performance tests for the task queue system."""

    @pytest.mark.asyncio
    async def test_1000_jobs_performance(self):
        """Submit 1000 jobs and track performance metrics."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            # Performance metrics
            metrics = {
                "total_jobs": 1000,
                "submission_start": time.time(),
                "submission_times": [],
                "job_ids": []
            }
            
            # Track initial memory
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"\n🚀 Starting 1000 jobs performance test...")
            print(f"Initial memory: {initial_memory:.2f} MB")
            
            # Create jobs with various priorities and types
            job_types = ["send_email", "data_export", "data_processing", "report_generation"]
            priorities = ["low", "normal", "high", "critical"]
            
            # Submit 1000 jobs
            for i in range(1000):
                job_start = time.time()
                
                job_data = {
                    "type": job_types[i % len(job_types)],
                    "priority": priorities[i % len(priorities)],
                    "payload": {
                        "batch_id": f"perf_test_{i}",
                        "data": f"test_data_{i}" * 10  # Some payload data
                    },
                    "resource_requirements": {
                        "cpu_units": 1 + (i % 3),  # 1-3 CPU units
                        "memory_mb": 128 + (i % 4) * 64  # 128-384 MB
                    }
                }
                
                response = await client.post("/jobs/", json=job_data)
                job_end = time.time()
                
                assert response.status_code == 200
                
                job_response = response.json()
                metrics["job_ids"].append(job_response["job_id"])
                metrics["submission_times"].append(job_end - job_start)
                
                # Track memory every 100 jobs
                if i % 100 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    print(f"  Jobs {i}: Memory {current_memory:.2f} MB")
            
            metrics["submission_end"] = time.time()
            
            # Calculate performance metrics
            total_time = metrics["submission_end"] - metrics["submission_start"]
            jobs_per_second = metrics["total_jobs"] / total_time
            avg_submission_time = sum(metrics["submission_times"]) / len(metrics["submission_times"])
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = final_memory - initial_memory
            
            print(f"\n📊 Performance Results:")
            print(f"  Total time: {total_time:.2f} seconds")
            print(f"  Jobs per second: {jobs_per_second:.2f}")
            print(f"  Average submission time: {avg_submission_time*1000:.2f} ms")
            print(f"  Memory growth: {memory_growth:.2f} MB")
            print(f"  Final memory: {final_memory:.2f} MB")
            
            # Performance assertions
            assert jobs_per_second > 50, f"Expected >50 jobs/sec, got {jobs_per_second:.2f}"
            assert memory_growth < 100, f"Memory growth too high: {memory_growth:.2f} MB"
            assert avg_submission_time < 0.1, f"Submission too slow: {avg_submission_time*1000:.2f} ms"
            
            print("✅ 1000 jobs performance test passed!")

    @pytest.mark.asyncio
    async def test_queue_operations_performance(self):
        """Test queue operations performance - should be O(log n) or better."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            print(f"\n⚡ Testing queue operations performance...")
            
            queue_sizes = [10, 50, 100, 500, 1000]
            operation_times = []
            
            for size in queue_sizes:
                print(f"  Testing with {size} jobs...")
                
                # Submit jobs
                start_time = time.time()
                job_ids = []
                
                for i in range(size):
                    job_data = {
                        "type": "test_job",
                        "priority": "normal",
                        "payload": {"test": f"queue_perf_{i}"},
                        "resource_requirements": {
                            "cpu_units": 1,
                            "memory_mb": 128
                        }
                    }
                    response = await client.post("/jobs/", json=job_data)
                    assert response.status_code == 200
                    job_ids.append(response.json()["job_id"])
                
                end_time = time.time()
                avg_time_per_op = (end_time - start_time) / size
                operation_times.append((size, avg_time_per_op))
                
                print(f"    Average time per operation: {avg_time_per_op*1000:.2f} ms")
            
            # Check that operations don't grow exponentially
            # For O(log n), the ratio should be roughly proportional to log(n2/n1)
            small_ops = operation_times[0][1]  # 10 jobs
            large_ops = operation_times[-1][1]  # 1000 jobs
            
            # For O(log n): log(1000)/log(10) = 3, so we expect ~3x time
            # We'll be generous and allow up to 10x
            ratio = large_ops / small_ops
            print(f"    Performance ratio (1000 vs 10 jobs): {ratio:.2f}x")
            
            assert ratio < 10, f"Queue operations too slow: {ratio:.2f}x growth"
            
            print("✅ Queue operations performance test passed!")

    @pytest.mark.asyncio
    async def test_resource_contention_performance(self):
        """Test system behavior under resource contention."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            print(f"\n🔥 Testing resource contention performance...")
            
            # Create heavy jobs that will compete for resources
            heavy_jobs = []
            light_jobs = []
            
            # 5 heavy jobs (4 CPU, 2048 MB each) - only 2 can run simultaneously
            for i in range(5):
                job_data = {
                    "type": "data_processing",
                    "priority": "high",
                    "payload": {"heavy_job": i},
                    "resource_requirements": {
                        "cpu_units": 4,
                        "memory_mb": 2048
                    }
                }
                response = await client.post("/jobs/", json=job_data)
                assert response.status_code == 200
                heavy_jobs.append(response.json()["job_id"])
            
            # 10 light jobs (1 CPU, 256 MB each) - should fit in gaps
            for i in range(10):
                job_data = {
                    "type": "send_email",
                    "priority": "normal",
                    "payload": {"light_job": i},
                    "resource_requirements": {
                        "cpu_units": 1,
                        "memory_mb": 256
                    }
                }
                response = await client.post("/jobs/", json=job_data)
                assert response.status_code == 200
                light_jobs.append(response.json()["job_id"])
            
            print(f"  Created {len(heavy_jobs)} heavy jobs and {len(light_jobs)} light jobs")
            
            # Wait a bit for jobs to start processing
            await asyncio.sleep(2)
            
            # Check job statuses
            running_heavy = 0
            running_light = 0
            
            for job_id in heavy_jobs:
                response = await client.get(f"/jobs/{job_id}")
                assert response.status_code == 200
                job = response.json()
                if job["status"] in ["RUNNING", "COMPLETED"]:
                    running_heavy += 1
            
            for job_id in light_jobs:
                response = await client.get(f"/jobs/{job_id}")
                assert response.status_code == 200
                job = response.json()
                if job["status"] in ["RUNNING", "COMPLETED"]:
                    running_light += 1
            
            print(f"  Heavy jobs running/completed: {running_heavy}")
            print(f"  Light jobs running/completed: {running_light}")
            
            # Resource contention should allow some light jobs to run
            # even when heavy jobs are competing
            assert running_light > 0, "Light jobs should be able to run alongside heavy jobs"
            
            print("✅ Resource contention performance test passed!") 