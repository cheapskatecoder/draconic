# 🚀 Task Queue System

A production-ready task queue system built with **FastAPI** that handles job scheduling, prioritization, and execution with real-world constraints.

## ✨ Features

- **🎯 Smart Job Scheduling**: Priority-based with dependency management
- **🔗 DAG Support**: Handle complex job dependencies with cycle detection
- **⚡ Resource Management**: CPU and memory allocation tracking
- **🔄 Retry Logic**: Exponential backoff with configurable attempts
- **📊 Real-time Updates**: WebSocket support for live job monitoring
- **🐳 Production Ready**: Docker containerization with proper logging
- **🧪 Comprehensive Testing**: Full test suite included

## 🏗 Architecture

```mermaid
graph TB
    API[FastAPI API] --> Scheduler[Task Scheduler]
    API --> DB[(PostgreSQL)]
    API --> Redis[(Redis Cache)]
    
    Scheduler --> ResourceManager[Resource Manager]
    Scheduler --> JobExecutor[Job Executor]
    Scheduler --> WebSocket[WebSocket Manager]
    
    JobExecutor --> Workers[Job Workers]
    Workers --> JobTypes[Email/Export/Report Jobs]
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- pyenv (recommended)

### 1. Clone and Setup

```bash
git clone <repository>
cd draconic

# Create virtual environment
pyenv virtualenv 3.11 draconic
pyenv activate draconic

# Install dependencies
pip install -r requirements.txt
```

### 2. Start with Docker

```bash
# Start all services (PostgreSQL, Redis, API, Worker)
docker-compose up -d

# Check logs
docker-compose logs -f app
```

### 3. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **WebSocket**: ws://localhost:8000/jobs/stream

## 📖 API Endpoints

### Job Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/jobs/` | Submit a new job |
| `GET` | `/jobs/{job_id}` | Get job status and details |
| `GET` | `/jobs/` | List jobs with filtering |
| `PATCH` | `/jobs/{job_id}/cancel` | Cancel a job |
| `GET` | `/jobs/{job_id}/logs` | Get job execution logs |
| `WebSocket` | `/jobs/stream` | Real-time job updates |

### Example Usage

#### Create a Job

```bash
curl -X POST "http://localhost:8000/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "data_export",
    "priority": "high",
    "payload": {
      "user_id": 123,
      "format": "csv"
    },
    "resource_requirements": {
      "cpu_units": 2,
      "memory_mb": 512
    },
    "retry_config": {
      "max_attempts": 3,
      "backoff_multiplier": 2
    }
  }'
```

#### Create Job with Dependencies

```bash
curl -X POST "http://localhost:8000/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "report_generation",
    "priority": "normal",
    "depends_on": ["job_id_1", "job_id_2"],
    "payload": {
      "report_type": "daily_summary",
      "date": "2024-01-15"
    }
  }'
```

## 🔧 Job Types

The system supports various job types out of the box:

- **`send_email`**: Email sending jobs
- **`data_export`**: Data export in various formats
- **`data_fetch`**: External API data fetching  
- **`data_processing`**: Data transformation tasks
- **`report_generation`**: Report creation jobs

## 🎯 Job States

```mermaid
graph LR
    PENDING --> READY
    PENDING --> BLOCKED
    BLOCKED --> READY
    READY --> RUNNING
    RUNNING --> COMPLETED
    RUNNING --> FAILED
    RUNNING --> TIMEOUT
    FAILED --> PENDING[Retry]
    TIMEOUT --> PENDING[Retry]
    READY --> CANCELLED
    PENDING --> CANCELLED
    BLOCKED --> CANCELLED
```

## ⚙️ Configuration

Key configuration options in `app/core/config.py`:

```python
# Worker settings
max_concurrent_jobs: int = 10
max_cpu_units: int = 8
max_memory_mb: int = 4096

# Job settings
default_job_timeout: int = 3600  # 1 hour
max_retry_attempts: int = 3
retry_backoff_multiplier: float = 2.0
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_jobs.py -v
```

## 📊 Monitoring

### WebSocket Events

Connect to `ws://localhost:8000/jobs/stream` to receive real-time updates:

```json
{
  "type": "job_update",
  "event": "job_started",
  "job_id": "uuid",
  "data": {
    "job_id": "uuid",
    "type": "send_email",
    "priority": "high",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

### Logging

Logs are structured and include:
- Job lifecycle events
- Resource allocation/deallocation
- Error tracking with stack traces
- Performance metrics

## 🔄 Development

### Project Structure

```
app/
├── main.py              # FastAPI application
├── core/                # Core configuration
├── models/              # SQLAlchemy models
├── routes/              # API routes
├── schemas/             # Pydantic schemas
├── services/            # Business logic
└── workers/             # Job execution

tests/                   # Test suite
migrations/              # Database migrations
```

### Adding New Job Types

1. Add handler to `app/workers/job_executor.py`:

```python
async def _handle_my_job_type(self, job: Job) -> Dict[str, Any]:
    # Your job logic here
    return {"result": "success"}
```

2. Register in `job_handlers` dict:

```python
self.job_handlers["my_job_type"] = self._handle_my_job_type
```

## 🐳 Production Deployment

### Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0
MAX_CONCURRENT_JOBS=20
MAX_CPU_UNITS=16
MAX_MEMORY_MB=8192
LOG_LEVEL=INFO
```

### Scaling

- **Horizontal**: Run multiple worker containers
- **Vertical**: Increase resource limits
- **Database**: Use connection pooling
- **Redis**: Use Redis Cluster for high availability

### Monitoring

- Health check endpoint: `/health`
- Prometheus metrics (extensible)
- Structured logging
- Database query performance tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

---

**Built with ❤️ using FastAPI, PostgreSQL, and Redis** 