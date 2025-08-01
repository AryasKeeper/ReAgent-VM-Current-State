#!/bin/bash

# ReAgent Environment Validation Script
# Validates required environment variables before starting services

set -e

echo "🔍 Validating ReAgent environment configuration..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found. Copy .env.example to .env and configure your API keys."
    exit 1
fi

# Source environment variables
set -a
source .env
set +a

# Validate OpenAI API Key
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-openai-api-key-here-replace-with-actual-key" ]; then
    echo "❌ ERROR: OPENAI_API_KEY is not configured or using placeholder value."
    echo "   Please set a valid OpenAI API key in .env file (format: sk-...)"
    exit 1
fi

# Validate OpenAI API Key format
if [[ ! "$OPENAI_API_KEY" =~ ^sk-[a-zA-Z0-9]{48}$ ]]; then
    echo "⚠️  WARNING: OPENAI_API_KEY format appears invalid. Expected format: sk-[48 characters]"
    echo "   Current: $OPENAI_API_KEY"
    echo "   Continuing anyway, but Weaviate may fail to start..."
fi

# Check if OpenAI API key looks like Google API key (common mistake)
if [[ "$OPENAI_API_KEY" =~ ^AIza ]]; then
    echo "❌ ERROR: OPENAI_API_KEY appears to be a Google API key (starts with 'AIza')"
    echo "   Please provide a valid OpenAI API key (starts with 'sk-')"
    exit 1
fi

# Validate required services environment
echo "✅ OpenAI API Key configured"

# Check Postgres configuration
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "❌ ERROR: POSTGRES_PASSWORD not configured"
    exit 1
fi
echo "✅ PostgreSQL configuration valid"

# Validate Weaviate URL
if [ -z "$WEAVIATE_URL" ]; then
    echo "❌ ERROR: WEAVIATE_URL not configured"
    exit 1
fi
echo "✅ Weaviate URL configured: $WEAVIATE_URL"

echo "🎉 Environment validation successful! All required configurations are present."
echo ""
echo "📋 Configuration Summary:"
echo "   - OpenAI API Key: Configured (${OPENAI_API_KEY:0:10}...)"
echo "   - PostgreSQL: $POSTGRES_USER@$POSTGRES_DB"
echo "   - Weaviate URL: $WEAVIATE_URL"
echo "   - Environment: $ENVIRONMENT"
echo ""