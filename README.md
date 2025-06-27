# 🚀 Draconic Task Queue System

A production-ready task queue system built with **FastAPI**, **PostgreSQL**, **Redis**, and **Docker**. Designed for high-performance job scheduling with intelligent prioritization, dependency management, and resource allocation.

## ✨ Features

- **🎯 Smart Scheduling**: Priority-based job execution with Redis queues
- **🔗 Dependency Management**: DAG-based job dependencies with cycle detection
- **⚡ Resource Allocation**: Atomic resource tracking with Redis transactions
- **🔄 Failure Handling**: Exponential backoff retry logic with dead letter queue
- **📊 Real-time Monitoring**: WebSocket updates and comprehensive metrics
- **🐳 Production Ready**: Docker containerization with health checks
- **🛡️ Admin Interface**: Management API for system operations

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   Worker Pool   │    │   Scheduler     │
│                 │    │                 │    │                 │
│ • REST API      │    │ • Job Execution │    │ • Queue Mgmt    │
│ • WebSocket     │    │ • Error Handling│    │ • Dependencies  │
│ • Admin Routes  │    │ • Retry Logic   │    │ • Resource Mgmt │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
         │   PostgreSQL    │    │     Redis       │    │   Dead Letter   │
         │                 │    │                 │    │     Queue       │
         │ • Job Metadata  │    │ • Priority Qs   │    │ • Failed Jobs   │
         │ • Dependencies  │    │ • Resource Lock │    │ • Retry Logic   │
         │ • Execution Log │    │ • Real-time Ops │    │ • Admin Mgmt    │
         └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚦 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)

### 1. Start the System
```bash
# Clone and start
git clone https://github.com/cheapskatecoder/draconic
cd draconic
docker-compose up -d

# Check status
docker-compose ps
```

### 2. Submit Your First Job
```bash
curl -X POST http://localhost:8000/jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "type": "send_email",
    "priority": "high",
    "payload": {
      "to": "user@example.com",
      "subject": "Welcome!"
    },
    "resource_requirements": {
      "cpu_units": 1,
      "memory_mb": 128
    }
  }'
```

### 3. Monitor Progress
```bash
# Get job status
curl http://localhost:8000/jobs/{job_id}

# List all jobs
curl http://localhost:8000/jobs/

# Get job logs
curl http://localhost:8000/jobs/{job_id}/logs

# System health
curl http://localhost:8000/admin/health
```

## 📋 API Endpoints

### Core Job Management
- `POST /jobs/` - Submit new job
- `GET /jobs/{job_id}` - Get job details
- `GET /jobs/` - List jobs with filtering
- `PATCH /jobs/{job_id}/cancel` - Cancel job
- `GET /jobs/{job_id}/logs` - Get execution logs
- `GET /jobs/stream` - WebSocket for real-time updates

### Admin & Monitoring
- `GET /admin/health` - System health check
- `GET /admin/metrics` - Performance metrics
- `GET /admin/dlq/` - Dead letter queue management
- `POST /admin/dlq/{job_id}/retry` - Retry failed job

## 🎯 Job Types & Priorities

### Supported Job Types
- `send_email` - Email notifications
- `data_export` - Data export operations
- `data_processing` - Heavy data processing
- `report_generation` - Report creation

### Priority Levels
- `critical` - Immediate execution
- `high` - High priority
- `normal` - Standard priority  
- `low` - Background tasks

## 🔗 Job Dependencies

Create complex workflows with job dependencies:

```json
{
  "type": "report_generation",
  "priority": "normal",
  "depends_on": ["data_fetch_job_id", "data_process_job_id"],
  "payload": {
    "report_type": "daily_summary"
  }
}
```

## ⚡ Performance

- **O(1) Queue Operations**: Redis-based priority queues
- **118+ jobs/sec**: Submission throughput
- **Sub-100ms**: Average job submission time
- **<25MB**: Memory growth for 1000 jobs
- **Atomic Resource Allocation**: No race conditions

## 🧪 Testing

```bash
# Run all tests
docker exec draconic-app-1 python -m pytest tests/ -v

# Core functionality tests
docker exec draconic-app-1 python -m pytest tests/test_jobs.py -v

# Performance tests
docker exec draconic-app-1 python -m pytest tests/test_performance.py -v

# Run performance benchmark
python run_performance_tests.py
```

## 🔧 Configuration

Environment variables in `docker-compose.yml`:

```yaml
environment:
  - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/taskqueue
  - REDIS_URL=redis://redis:6379/0
  - MAX_CPU_UNITS=8
  - MAX_MEMORY_MB=4096
  - LOG_LEVEL=INFO
```

## 📊 Monitoring & Observability

### Health Checks
```bash
curl http://localhost:8000/admin/health
```

### Metrics Dashboard
```bash
curl http://localhost:8000/admin/metrics
```

### Real-time Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/jobs/stream');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Job update:', update);
};
```

## 🐛 Troubleshooting

### Common Issues

**Jobs stuck in PENDING**
- Check resource availability: `curl http://localhost:8000/admin/metrics`
- Verify dependencies are completed

**High memory usage**
- Monitor with: `docker stats`
- Check for memory leaks in job handlers

**Redis connection errors**
- Restart Redis: `docker-compose restart redis`
- Check Redis logs: `docker logs draconic-redis-1`

### Debug Logs
```bash
# App logs
docker logs draconic-app-1 -f

# Worker logs  
docker logs draconic-worker-1 -f

# Database logs
docker logs draconic-postgres-1 -f
```

## 🚀 Production Deployment

### Scaling
```yaml
# docker-compose.prod.yml
services:
  worker:
    scale: 4  # Multiple workers
  
  app:
    deploy:
      replicas: 2  # Load balanced API
```

### Security
- Use environment secrets for passwords
- Enable TLS for external access
- Configure firewall rules
- Regular security updates

## 📚 Development

### Local Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start services
docker-compose up postgres redis -d

# Run locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Code Structure
```
app/
├── main.py              # FastAPI application
├── core/                # Core configuration
├── models/              # Database models
├── routes/              # API endpoints
├── services/            # Business logic
├── workers/             # Job execution
└── schemas/             # Pydantic schemas
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
