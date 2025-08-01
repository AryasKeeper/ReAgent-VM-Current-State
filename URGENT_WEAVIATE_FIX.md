# 🚨 URGENT: Weaviate OpenAI API Key Fix

## **IMMEDIATE ACTION REQUIRED**

Your ReAgent deployment is failing because Weaviate cannot start due to an invalid OpenAI API key configuration.

## **🔥 CRITICAL ISSUE**
- Weaviate is continuously restarting with error: `invalid apikey config: keys cannot have length 0`
- Current .env contains placeholder OpenAI API key: `sk-your-openai-api-key-here-replace-with-actual-key`
- This is blocking all ReAgent services including Gemini's frontend development

## **⚡ INSTANT FIX COMMANDS**

### Step 1: Stop All Services
```bash
docker compose down
```

### Step 2: Update OpenAI API Key in .env
```bash
# Open .env file
nano .env

# Replace this line:
OPENAI_API_KEY=sk-your-openai-api-key-here-replace-with-actual-key

# With your actual OpenAI API key:
OPENAI_API_KEY=sk-your-actual-openai-api-key-goes-here
```

### Step 3: Validate Configuration
```bash
./scripts/validate_env.sh
```

### Step 4: Start Services in Correct Order
```bash
# Start core services
docker compose up -d postgres redis

# Wait for core services (10 seconds)
sleep 10

# Start Weaviate
docker compose up -d weaviate

# Wait for Weaviate (15 seconds)
sleep 15

# Check Weaviate status
docker compose ps weaviate

# If healthy, start remaining services
docker compose up -d
```

## **🔑 OpenAI API Key Requirements**

Your OpenAI API key must:
- Start with `sk-`
- Be exactly 51 characters long
- Look like: `sk-1234567890abcdef1234567890abcdef12345678901`
- Be obtained from: https://platform.openai.com/api-keys

## **✅ Success Verification**

After fixing, you should see:
```bash
docker compose ps
# All services should show "Up" or "Up (healthy)"

docker compose logs weaviate
# Should show successful startup without "invalid apikey" errors
```

## **🚀 Automated Fix Script**

For convenience, run the automated fix:
```bash
./scripts/fix_weaviate_config.sh
```

## **📞 Next Steps for Gemini**

Once Weaviate is running:
1. Verify vector search is working: `curl http://localhost:8080/v1/.well-known/ready`
2. Check all services are healthy: `docker compose ps`
3. Frontend development can proceed with working backend APIs

## **🛟 Emergency Contacts**

If this fix doesn't work:
1. Check logs: `docker compose logs weaviate`
2. Run troubleshooting: `cat scripts/weaviate_troubleshooting.md`
3. Validate environment: `./scripts/validate_env.sh`

**STATUS: CRITICAL - BLOCKING DEPLOYMENT**
**PRIORITY: IMMEDIATE ACTION REQUIRED**