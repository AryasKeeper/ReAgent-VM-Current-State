#!/bin/bash

# ReAgent Weaviate Emergency Fix Script
# =====================================
# This script applies the critical Weaviate OIDC authentication fixes

set -e

echo "🚨 WEAVIATE EMERGENCY FIX DEPLOYMENT"
echo "====================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo "⚠️  Please edit .env and add your actual OPENAI_API_KEY"
    echo "⚠️  Current placeholder will cause OpenAI integration to fail"
fi

# Stop existing Weaviate container
echo ""
echo "🛑 Stopping existing Weaviate container..."
docker compose stop weaviate || true
docker compose rm -f weaviate || true

# Pull new Weaviate image
echo ""
echo "📥 Pulling Weaviate 1.24.1 image..."
docker pull cr.weaviate.io/semitechnologies/weaviate:1.24.1

# Start Weaviate with new configuration
echo ""
echo "🚀 Starting Weaviate with fixed configuration..."
docker compose up -d weaviate

# Wait for startup
echo ""
echo "⏳ Waiting for Weaviate to start..."
sleep 15

# Check container status
echo ""
echo "🔍 Checking container status..."
docker compose ps weaviate

# Check container logs for any OIDC errors
echo ""
echo "📋 Checking recent logs for OIDC errors..."
docker compose logs --tail=20 weaviate | grep -i "oidc\|unauthorized\|authentication" || echo "No authentication errors found ✅"

# Run validation script
echo ""
echo "🔬 Running validation tests..."
python3 validate_weaviate_fix.py

echo ""
echo "🎉 WEAVIATE EMERGENCY FIX COMPLETE!"
echo ""
echo "Next steps:"
echo "1. If validation passed, start full system: docker-compose up -d"
echo "2. If OpenAI test failed, verify OPENAI_API_KEY in .env file"
echo "3. Monitor logs: docker-compose logs -f weaviate"