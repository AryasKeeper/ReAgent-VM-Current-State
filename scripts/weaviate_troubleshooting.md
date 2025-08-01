# Weaviate Troubleshooting Guide

## Common Issues and Solutions

### 1. OpenAI API Key Configuration

**Error:** `invalid apikey config: keys cannot have length 0`

**Cause:** 
- Missing or empty OpenAI API key
- Wrong API key format (Google API key instead of OpenAI)
- Placeholder values not replaced

**Solution:**
```bash
# Check current configuration
grep OPENAI_API_KEY .env

# Valid format should be:
OPENAI_API_KEY=sk-1234567890abcdef1234567890abcdef12345678901

# Run validation script
./scripts/validate_env.sh
```

### 2. Service Startup Order

**Error:** Weaviate starts before environment is ready

**Solution:**
```bash
# Start services in correct order
docker-compose up -d postgres redis
sleep 10
docker-compose up -d weaviate
sleep 15
docker-compose up -d
```

### 3. Environment File Loading

**Error:** Environment variables not loaded properly

**Solution:**
```bash
# Ensure .env file exists and is readable
ls -la .env
cat .env | grep -E "OPENAI|WEAVIATE"

# Restart with clean state
docker-compose down --volumes
docker-compose up -d
```

### 4. Weaviate Module Configuration

**Error:** `text2vec-openai` module not loading

**Solution:**
Check docker-compose.yml configuration:
```yaml
weaviate:
  environment:
    DEFAULT_VECTORIZER_MODULE: 'text2vec-openai'
    ENABLE_MODULES: 'text2vec-openai,generative-openai'
    OPENAI_APIKEY: ${OPENAI_API_KEY:-}
```

### 5. Container Dependencies

**Error:** Services failing due to Weaviate dependency

**Solution:**
```bash
# Check service health
docker-compose ps
docker-compose logs weaviate

# Restart dependent services
docker-compose restart celery-worker agents api
```

## Diagnostic Commands

```bash
# Check Weaviate logs
docker-compose logs -f weaviate

# Test Weaviate API
curl http://localhost:8080/v1/.well-known/ready

# Check OpenAI integration
curl -H "Content-Type: application/json" \
     -d '{"query": "{Get{Property{title}}}"}' \
     http://localhost:8080/v1/graphql

# Validate environment
./scripts/validate_env.sh

# Full system status
docker-compose ps
```

## Prevention

1. Always validate environment before starting:
   ```bash
   ./scripts/validate_env.sh
   ```

2. Use the fix script for automated recovery:
   ```bash
   ./scripts/fix_weaviate_config.sh
   ```

3. Monitor startup logs:
   ```bash
   docker-compose up -d && docker-compose logs -f weaviate
   ```

## Quick Recovery Steps

1. Stop all services: `docker-compose down`
2. Validate configuration: `./scripts/validate_env.sh`
3. Fix issues in .env file
4. Start with fix script: `./scripts/fix_weaviate_config.sh`
5. Monitor logs: `docker-compose logs -f weaviate`