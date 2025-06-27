Sure! Here's the entire Backend Engineer Case Study converted to well-structured **Markdown**:

---

# 🧠 Backend Engineer Case Study: Smart Task Queue System

Build a production-ready task queue system using **FastAPI** that handles job scheduling, prioritization, and execution with real-world constraints.

**⏱ Suggested Time**: 2–3 hours of focused work

---

## 📌 The Challenge

Your company needs a task queue system that processes background jobs for a real-time fintech platform. Jobs range from sending emails to processing large data exports.

The system must intelligently handle:

* ✅ Priorities
* ✅ Dependencies
* ✅ Resource constraints

---

## 📋 Core Requirements

### 1. API Endpoints

Create a **FastAPI** application with the following endpoints:

| Endpoint                | Method    | Description                     |
| ----------------------- | --------- | ------------------------------- |
| `/jobs`                 | POST      | Submit a new job                |
| `/jobs/{job_id}`        | GET       | Get job status and details      |
| `/jobs`                 | GET       | List jobs with filtering        |
| `/jobs/{job_id}/cancel` | PATCH     | Cancel a job if possible        |
| `/jobs/{job_id}/logs`   | GET       | Get job execution logs          |
| `/jobs/stream`          | WebSocket | WebSocket for real-time updates |

---

### 2. Job Model

Jobs should support:

* 🧩 Different types (`email`, `data_export`, `report_generation`, etc.)
* 🏷 Priority levels: `critical`, `high`, `normal`, `low`
* 🔗 Dependencies on other jobs
* ⚙️ Resource requirements: CPU units, memory (MB)
* ♻️ Retry configuration
* ⏱ Timeout configuration (`timeout_seconds`)
* 📅 Status tracking with timestamps

---

### 3. Core Features

* 🚦 **Smart Scheduling**: Based on priority, dependencies, and available resources
* 🔗 **Dependency Management**: Handle job dependency execution flow
* 📉 **Resource Allocation**: Prevent system overload
* 💥 **Failure Handling**: Retry with exponential backoff
* 🔁 **Idempotency**: Avoid duplicate job execution

---

### 4. Production Considerations

* 🧵 Concurrent job execution (simulate with `asyncio.sleep`)
* 🧼 Graceful shutdown (complete running jobs)
* ⌛ Job timeout handling
* 🧾 Proper error messages and status codes
* 📊 Basic monitoring metrics

---

### ✅ Example Input

```http
POST /jobs
Content-Type: application/json
```

```json
{
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
  "depends_on": ["job_abc123"],
  "retry_config": {
    "max_attempts": 3,
    "backoff_multiplier": 2
  }
}
```

**Response:**

```json
{
  "job_id": "job_xyz789",
  "status": "pending",
  "created_at": "2024-01-15T10:00:00Z",
  "priority": "high",
  "position_in_queue": 5
}
```

---

## 🗄 Implementation Guidelines

### Database Schema

Design PostgreSQL tables for:

* Job metadata and status
* Dependency relationships (DAG structure)
* Execution history and logs
* Resource allocation tracking

### Key Technical Decisions

* How to handle job dependencies?
* How to allocate resources fairly?
* Retry vs permanent fail?
* How to handle concurrent updates?

### Performance Considerations

* Millions of rows in `jobs` table
* Status queries should be fast
* Queue operations should be **O(log n)** or better
* Use indexes wisely

---

## 📦 Deliverables

```
your-name-task-queue/
├── app/
│   ├── main.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── workers/
├── tests/
├── migrations/
├── docker-compose.yml
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
├── AI_USAGE.md
└── evaluation_results.md
```

---

## 📄 Required Documentation

* ✅ `README.md`: Setup instructions
* ✅ `ARCHITECTURE.md`: Key design decisions
* ✅ `AI_USAGE.md`: AI/chat history if applicable
* ✅ `evaluation_results.md`: Test run metrics and performance

---

## 🧪 Evaluation Criteria

We’re looking for:

* System Design Thinking
* Production-Readiness
* Efficient DB schema
* Code quality + testing
* Performance Awareness
* Edge case problem-solving

---

## 🧾 Test Scenarios

---

### 🔹 Scenario 1: Basic Job Flow

```json
[
  {
    "type": "send_email",
    "priority": "normal",
    "payload": {"to": "user@example.com", "template": "welcome"},
    "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
  },
  {
    "type": "send_email",
    "priority": "critical",
    "payload": {"to": "vip@example.com", "template": "alert"},
    "resource_requirements": {"cpu_units": 1, "memory_mb": 128}
  },
  {
    "type": "generate_report",
    "priority": "low",
    "payload": {"report_type": "daily_summary", "date": "2024-01-15"},
    "resource_requirements": {"cpu_units": 4, "memory_mb": 2048}
  }
]
```

✅ Expected:

* Critical job runs first
* Proper priority order
* Resource tracking correct

---

### 🔹 Scenario 2: Simple Dependencies

```json
[
  {
    "job_id": "fetch_data_001",
    "type": "data_fetch",
    "priority": "high",
    "payload": {"source": "market_api", "symbols": ["AAPL", "GOOGL"]},
    "resource_requirements": {"cpu_units": 2, "memory_mb": 512}
  },
  {
    "job_id": "process_data_001",
    "type": "data_processing",
    "priority": "high",
    "depends_on": ["fetch_data_001"],
    "resource_requirements": {"cpu_units": 4, "memory_mb": 1024}
  },
  {
    "job_id": "generate_report_001",
    "type": "report_generation",
    "priority": "normal",
    "depends_on": ["process_data_001"],
    "resource_requirements": {"cpu_units": 2, "memory_mb": 512}
  }
]
```

✅ Expected:

* Executes in dependency order
* Dependent jobs don’t run on parent failure
* Status reflects `blocked` → `ready`

---

### 🔹 Scenario 3: Complex Dependency Graph

Includes DAG with jobs like:

```text
fetch_prices ─┐
              ├── analyze_market ─┐
fetch_volumes ┘                   ├── trader_report
                                  ├── risk_report
                                  └── send_notifications
```

✅ Expected:

* DAG is respected
* Execution happens in topological order

---

### 🔹 Scenario 4: Resource Contention

> System capacity: `8 CPU`, `4096 MB`

Includes:

* 5 heavy jobs (`4 CPU`, `2048 MB`) → Only 2 can run simultaneously
* 5 light jobs (`1 CPU`, `256 MB`) → Should fit between gaps

✅ Expected:

* No resource overflow
* Priority respected
* Fairness + efficient slot filling

---

### 🔹 Scenario 5: Failure and Recovery

Includes:

* Retry logic with backoff
* Timeout behavior
* Permanent failures
* Dependency failure propagation

✅ Expected:

* Retries work correctly
* Timeout triggers retries
* Failed parents prevent child execution

---

### 🔹 Bonus: Circular Dependencies

```json
[
  {"job_id": "job_a", "depends_on": ["job_c"]},
  {"job_id": "job_b", "depends_on": ["job_a"]},
  {"job_id": "job_c", "depends_on": ["job_b"]}
]
```

🛑 Expected:

* Cycle detection prevents job execution
* Return error with cycle info

---

## 🚀 Performance Test

* Submit **1000 jobs** (various priorities)
* Track:

| Metric            | Description           |
| ----------------- | --------------------- |
| Time to accept    | All submissions       |
| Queue ops speed   | Enqueue/dequeue times |
| Memory growth     | Under load            |
| Query performance | At scale              |

---

## 📊 Evaluation Metrics

* ✅ Correctness: Jobs in right order?
* ⚙️ Performance: Efficient operations?
* 🔒 Resource Safety: No oversubscription?
* 💥 Failure Handling: Retry + backoff?
* 👁 Observability: Logs + metrics visible?

---

## 🌟 Bonus Features (Optional)

* 🕒 Cron-style job scheduling
* ⏫ Priority boost for old jobs
* 📭 Dead letter queue
* 🧑‍💻 Basic admin UI
* 🛡 Distributed locking

---

Let me know if you'd like a starter template repo or breakdown for implementation.
