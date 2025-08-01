#!/bin/bash

# ReAgent Sydney - Deployment Validation Script
# Comprehensive testing for all services and integrations

set -e

echo "🧪 REAGENT SYDNEY - DEPLOYMENT VALIDATION"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results tracking
PASSED=0
FAILED=0

# Function to run test with status reporting
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Testing $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        ((FAILED++))
        return 1
    fi
}

# Function to run test with output capture
run_test_with_output() {
    local test_name="$1"
    local test_command="$2"
    
    echo "Testing $test_name..."
    
    if output=$(eval "$test_command" 2>&1); then
        echo -e "${GREEN}✅ PASSED${NC}"
        echo "   Output: $output"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "   Error: $output"
        ((FAILED++))
        return 1
    fi
}

echo "🔍 Step 1: Container Status Validation"
echo "--------------------------------------"

# Check if containers are running
run_test "PostgreSQL container" "docker compose ps postgres | grep -q 'Up'"
run_test "Redis container" "docker compose ps redis | grep -q 'Up'"
run_test "Weaviate container" "docker compose ps weaviate | grep -q 'Up'"
run_test "API container" "docker compose ps api | grep -q 'Up'"
run_test "Agents container" "docker compose ps agents | grep -q 'Up'"
run_test "Celery Worker container" "docker compose ps celery-worker | grep -q 'Up'"
run_test "Celery Beat container" "docker compose ps celery-beat | grep -q 'Up'"

echo ""
echo "🌐 Step 2: Network Connectivity Tests"
echo "------------------------------------"

# Test service connectivity
run_test "PostgreSQL connection" "docker exec reagent-postgres pg_isready -U reagent_user -d reagent"
run_test "Redis connection" "docker exec reagent-redis redis-cli ping | grep -q PONG"
run_test "Weaviate ready endpoint" "curl -f http://localhost:8080/v1/.well-known/ready"
run_test "Weaviate live endpoint" "curl -f http://localhost:8080/v1/.well-known/live"
run_test "API health endpoint" "curl -f http://localhost:8000/health"

echo ""
echo "🔧 Step 3: Environment Variable Validation"
echo "-----------------------------------------"

# Check critical environment variables in containers
run_test "Weaviate OpenAI API key" "docker exec reagent-weaviate printenv OPENAI_APIKEY | grep -q sk-"
run_test "API OpenAI API key" "docker exec reagent-api printenv OPENAI_API_KEY | grep -q sk-"
run_test "API database URL" "docker exec reagent-api printenv DATABASE_URL | grep -q postgresql"
run_test "API Redis URL" "docker exec reagent-api printenv REDIS_URL | grep -q redis"
run_test "API Weaviate URL" "docker exec reagent-api printenv WEAVIATE_URL | grep -q weaviate"

echo ""
echo "🧠 Step 4: Weaviate OpenAI Integration Test"
echo "------------------------------------------"

# Test Weaviate OpenAI integration
echo "Testing Weaviate meta information..."
if curl -s http://localhost:8080/v1/meta | grep -q "text2vec-openai"; then
    echo -e "${GREEN}✅ PASSED${NC} - text2vec-openai module loaded"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED${NC} - text2vec-openai module not found"
    ((FAILED++))
fi

# Test OpenAI API key validation
echo "Testing OpenAI API key validation..."
OPENAI_TEST=$(curl -s -X POST http://localhost:8080/v1/schema \
  -H "Content-Type: application/json" \
  -d '{
    "class": "TestClass",
    "vectorizer": "text2vec-openai",
    "properties": [
      {
        "name": "description",
        "dataType": ["text"]
      }
    ]
  }')

if echo "$OPENAI_TEST" | grep -q "class.*TestClass" || echo "$OPENAI_TEST" | grep -q "already exists"; then
    echo -e "${GREEN}✅ PASSED${NC} - OpenAI integration working"
    ((PASSED++))
    
    # Clean up test class
    curl -s -X DELETE http://localhost:8080/v1/schema/TestClass > /dev/null 2>&1
else
    echo -e "${RED}❌ FAILED${NC} - OpenAI integration failed"
    echo "   Response: $OPENAI_TEST"
    ((FAILED++))
fi

echo ""
echo "💾 Step 5: Database Integration Test"
echo "----------------------------------"

# Test database connectivity from API service
run_test "Database connection from API" "docker exec reagent-api python -c 'import psycopg2; conn = psycopg2.connect(\"postgresql://reagent_user:\$POSTGRES_PASSWORD@postgres:5432/reagent\"); conn.close()'"

# Test Redis connectivity from API service
run_test "Redis connection from API" "docker exec reagent-api python -c 'import redis; r = redis.Redis.from_url(\"redis://redis:6379\"); r.ping()'"

echo ""
echo "⚡ Step 6: Performance and Resource Tests"
echo "---------------------------------------"

# Check container resource usage
echo "Container resource usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "📊 VALIDATION SUMMARY"
echo "===================="
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo "Total Tests: $((PASSED + FAILED))"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo "🚀 ReAgent Sydney deployment is fully operational!"
    echo ""
    echo "✅ Ready for:"
    echo "   - Multi-agent real estate intelligence"
    echo "   - Vector search with OpenAI embeddings"
    echo "   - Property data processing and analysis"
    echo "   - Production deployment"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}⚠️  SOME TESTS FAILED${NC}"
    echo "Please review the failed tests above and fix issues before proceeding."
    echo ""
    echo "Common fixes:"
    echo "- Ensure all environment variables are set in .env file"
    echo "- Check container logs: docker compose logs [service-name]"
    echo "- Restart failed services: docker compose restart [service-name]"
    echo ""
    exit 1
fi