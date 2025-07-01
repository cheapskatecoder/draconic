#!/bin/bash

# Draconic Task Queue System - API Test Script
# This script demonstrates all available API endpoints

BASE_URL="http://localhost:8000"

echo "🚀 Draconic Task Queue System - API Test Script"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print section headers
print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Function to print test descriptions
print_test() {
    echo -e "\n${YELLOW}📋 $1${NC}"
}

# Function to check if service is running
check_service() {
    echo -e "${YELLOW}🔍 Checking if service is running...${NC}"
    if curl -s "$BASE_URL/docs" > /dev/null; then
        echo -e "${GREEN}✅ Service is running!${NC}"
    else
        echo -e "${RED}❌ Service is not running. Please start with: docker-compose up -d${NC}"
        exit 1
    fi
}

# Check service first
check_service

print_section "1. BASIC JOB OPERATIONS"

print_test "Creating a simple email job"
echo -e "${BLUE}POST /jobs/ - Create email job${NC}"
EMAIL_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "send_email",
    "priority": "normal",
    "payload": {
      "to": "user@example.com",
      "subject": "Welcome!",
      "body": "Thanks for joining us!"
    },
    "resource_requirements": {
      "cpu_units": 1,
      "memory_mb": 128
    }
  }')

echo "$EMAIL_JOB_HEADERS" | sed '/^$/q'
EMAIL_JOB_ID=$(echo "$EMAIL_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}Created job ID: $EMAIL_JOB_ID${NC}"

print_test "Creating a high priority data export job"
echo -e "${BLUE}POST /jobs/ - Create data export job${NC}"
EXPORT_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "data_export",
    "priority": "high",
    "payload": {
      "user_id": 123,
      "format": "csv",
      "filters": {"date_range": "last_30_days"}
    },
    "resource_requirements": {
      "cpu_units": 2,
      "memory_mb": 512
    },
    "retry_config": {
      "max_attempts": 3,
      "backoff_multiplier": 2
    }
  }')

echo "$EXPORT_JOB_HEADERS" | sed '/^$/q'
EXPORT_JOB_ID=$(echo "$EXPORT_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}Created job ID: $EXPORT_JOB_ID${NC}"

print_test "Creating a critical report generation job"
echo -e "${BLUE}POST /jobs/ - Create report generation job${NC}"
REPORT_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "report_generation",
    "priority": "critical",
    "payload": {
      "report_type": "financial_summary",
      "period": "Q4_2024"
    },
    "resource_requirements": {
      "cpu_units": 4,
      "memory_mb": 1024
    },
    "timeout_seconds": 3600
  }')

echo "$REPORT_JOB_HEADERS" | sed '/^$/q'
REPORT_JOB_ID=$(echo "$REPORT_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}Created job ID: $REPORT_JOB_ID${NC}"

print_section "2. JOB DEPENDENCIES"

print_test "Creating a data fetch job (parent)"
echo -e "${BLUE}POST /jobs/ - Create data fetch job${NC}"
FETCH_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "data_fetch",
    "priority": "high",
    "payload": {
      "source": "market_api",
      "symbols": ["AAPL", "GOOGL", "MSFT"]
    },
    "resource_requirements": {
      "cpu_units": 2,
      "memory_mb": 256
    }
  }')

echo "$FETCH_JOB_HEADERS" | sed '/^$/q'
FETCH_JOB_ID=$(echo "$FETCH_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}Created fetch job ID: $FETCH_JOB_ID${NC}"

sleep 2

print_test "Creating a data processing job (depends on fetch)"
echo -e "${BLUE}POST /jobs/ - Create data processing job with dependency${NC}"
PROCESS_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"data_processing\",
    \"priority\": \"high\",
    \"depends_on\": [\"$FETCH_JOB_ID\"],
    \"payload\": {
      \"algorithm\": \"moving_average\",
      \"window\": 30
    },
    \"resource_requirements\": {
      \"cpu_units\": 4,
      \"memory_mb\": 1024
    }
  }")

echo "$PROCESS_JOB_HEADERS" | sed '/^$/q'
PROCESS_JOB_ID=$(echo "$PROCESS_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}Created process job ID: $PROCESS_JOB_ID${NC}"

print_test "Creating a final report job (depends on processing)"
echo -e "${BLUE}POST /jobs/ - Create final report job with dependency${NC}"
FINAL_REPORT_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"report_generation\",
    \"priority\": \"normal\",
    \"depends_on\": [\"$PROCESS_JOB_ID\"],
    \"payload\": {
      \"report_type\": \"market_analysis\",
      \"include_charts\": true
    },
    \"resource_requirements\": {
      \"cpu_units\": 2,
      \"memory_mb\": 512
    }
  }")

echo "$FINAL_REPORT_JOB_HEADERS" | sed '/^$/q'
FINAL_REPORT_JOB_ID=$(echo "$FINAL_REPORT_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo -e "${GREEN}Created final report job ID: $FINAL_REPORT_JOB_ID${NC}"

print_section "3. JOB MONITORING"

print_test "Getting job details for email job"
echo -e "${BLUE}GET /jobs/{job_id} - Get email job details${NC}"
curl -i -s "$BASE_URL/jobs/$EMAIL_JOB_ID" | sed '/^$/q'

print_test "Getting job details for export job"
echo -e "${BLUE}GET /jobs/{job_id} - Get export job details${NC}"
curl -i -s "$BASE_URL/jobs/$EXPORT_JOB_ID" | sed '/^$/q'

print_test "Listing all jobs"
echo -e "${BLUE}GET /jobs/ - List all jobs${NC}"
curl -i -s "$BASE_URL/jobs/" | sed '/^$/q'

print_test "Listing jobs by status (filtering for PENDING)"
echo -e "${BLUE}GET /jobs/?status=PENDING - Filter jobs by status${NC}"
curl -i -s "$BASE_URL/jobs/?status=PENDING" | sed '/^$/q'

print_test "Listing jobs by priority (filtering for HIGH)"
echo -e "${BLUE}GET /jobs/?priority=HIGH - Filter jobs by priority${NC}"
curl -i -s "$BASE_URL/jobs/?priority=HIGH" | sed '/^$/q'

print_test "Getting job logs for email job"
echo -e "${BLUE}GET /jobs/{job_id}/logs - Get job logs${NC}"
curl -i -s "$BASE_URL/jobs/$EMAIL_JOB_ID/logs" | sed '/^$/q'

print_section "4. JOB MANAGEMENT"

print_test "Attempting to cancel the final report job"
echo -e "${BLUE}PATCH /jobs/{job_id}/cancel - Cancel job${NC}"
curl -i -s -X PATCH "$BASE_URL/jobs/$FINAL_REPORT_JOB_ID/cancel" | sed '/^$/q'

print_test "Checking cancelled job status"
echo -e "${BLUE}GET /jobs/{job_id} - Check cancelled job status${NC}"
curl -i -s "$BASE_URL/jobs/$FINAL_REPORT_JOB_ID" | sed '/^$/q'

print_section "5. ADMIN & MONITORING"

print_test "System health check"
echo -e "${BLUE}GET /admin/health - System health check${NC}"
curl -i -s "$BASE_URL/admin/health" | sed '/^$/q'

print_test "System metrics"
echo -e "${BLUE}GET /admin/metrics - System metrics${NC}"
curl -i -s "$BASE_URL/admin/metrics" | sed '/^$/q'

print_test "Dead letter queue status"
echo -e "${BLUE}GET /admin/dlq/ - Dead letter queue status${NC}"
curl -i -s "$BASE_URL/admin/dlq/" | sed '/^$/q'

print_section "6. ERROR HANDLING"

print_test "Testing invalid job ID"
echo -e "${BLUE}GET /jobs/{invalid_job_id} - Test invalid job ID${NC}"
curl -i -s "$BASE_URL/jobs/00000000-0000-0000-0000-000000000000" | sed '/^$/q'

print_test "Testing invalid job creation (missing required fields)"
echo -e "${BLUE}POST /jobs/ - Test invalid job creation${NC}"
curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "invalid": "data"
  }' | sed '/^$/q'

print_test "Testing circular dependency (should fail)"
echo -e "${BLUE}POST /jobs/ - Create circular dependency job A${NC}"
CIRCULAR_JOB_A_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test_job",
    "priority": "normal",
    "payload": {"test": "circular_a"},
    "resource_requirements": {
      "cpu_units": 1,
      "memory_mb": 128
    }
  }')

echo "$CIRCULAR_JOB_A_HEADERS" | sed '/^$/q'
CIRCULAR_JOB_A_ID=$(echo "$CIRCULAR_JOB_A_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

# Try to create job B that depends on A, then update A to depend on B (this should fail)
echo -e "${BLUE}POST /jobs/ - Create circular dependency job B${NC}"
CIRCULAR_JOB_B_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"test_job\",
    \"priority\": \"normal\",
    \"depends_on\": [\"$CIRCULAR_JOB_A_ID\"],
    \"payload\": {\"test\": \"circular_b\"},
    \"resource_requirements\": {
      \"cpu_units\": 1,
      \"memory_mb\": 128
    }
  }")

echo "$CIRCULAR_JOB_B_HEADERS" | sed '/^$/q'

print_section "7. BULK OPERATIONS"

print_test "Creating multiple jobs quickly"
for i in {1..5}; do
    echo -e "${BLUE}POST /jobs/ - Create bulk job $i${NC}"
    BULK_JOB_HEADERS=$(curl -i -s -X POST "$BASE_URL/jobs/" \
      -H "Content-Type: application/json" \
      -d "{
        \"type\": \"send_email\",
        \"priority\": \"low\",
        \"payload\": {
          \"to\": \"bulk_user_$i@example.com\",
          \"subject\": \"Bulk Email $i\"
        },
        \"resource_requirements\": {
          \"cpu_units\": 1,
          \"memory_mb\": 64
        }
      }")
    
    echo "$BULK_JOB_HEADERS" | sed '/^$/q'
    BULK_JOB_ID=$(echo "$BULK_JOB_HEADERS" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}Created bulk job $i: $BULK_JOB_ID${NC}"
done

print_section "8. FINAL STATUS CHECK"

print_test "Final job listing to see all created jobs"
echo -e "${BLUE}GET /jobs/ - Final job listing${NC}"
curl -i -s "$BASE_URL/jobs/" | sed '/^$/q'

print_test "System metrics after test run"
echo -e "${BLUE}GET /admin/metrics - Final system metrics${NC}"
curl -i -s "$BASE_URL/admin/metrics" | sed '/^$/q'

echo -e "\n${GREEN}🎉 API test script completed!${NC}"
echo -e "${YELLOW}💡 You can also access the interactive API docs at: $BASE_URL/docs${NC}"
echo -e "${YELLOW}📊 Monitor real-time updates via WebSocket at: ws://localhost:8000/jobs/stream${NC}"
echo -e "${YELLOW}🔍 Check Docker logs with: docker logs draconic-app-1 -f${NC}" 