#!/bin/bash

# ReAgent Weaviate Configuration Fix Script
# Fixes the critical Weaviate OpenAI API key configuration issue

set -e

echo "🔧 ReAgent Weaviate Configuration Fix"
echo "====================================="

# Stop any running services
echo "🛑 Stopping existing services..."
docker-compose down --remove-orphans || true

# Clean up any dangling containers
echo "🧹 Cleaning up containers..."
docker container prune -f || true

# Check current .env configuration
echo ""
echo "📋 Current .env OpenAI configuration:"
grep -E "OPENAI_API_KEY" .env || echo "No OPENAI_API_KEY found"

echo ""
echo "🔍 Detected Issues:"
if grep -q "AIzaSy" .env; then
    echo "   ❌ Google API key detected instead of OpenAI API key"
fi
if grep -q "sk-your-openai-api-key-here" .env; then
    echo "   ❌ Placeholder OpenAI API key detected"
fi

echo ""
echo "🔑 OpenAI API Key Setup Required"
echo "================================"
echo ""
echo "To complete the fix, you need to:"
echo "1. Get your OpenAI API key from https://platform.openai.com/api-keys"
echo "2. Replace the placeholder in .env file with your actual API key"
echo ""
echo "Your OpenAI API key should:"
echo "   - Start with 'sk-'"
echo "   - Be exactly 51 characters long"
echo "   - Look like: sk-1234567890abcdef1234567890abcdef12345678901"
echo ""

# Offer to open .env file for editing
read -p "🛠️  Open .env file for editing now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v nano &> /dev/null; then
        nano .env
    elif command -v vim &> /dev/null; then
        vim .env  
    else
        echo "No text editor found. Please manually edit .env file."
    fi
fi

echo ""
echo "🧪 Testing configuration after changes..."
if ./scripts/validate_env.sh; then
    echo ""
    echo "✅ Configuration validated successfully!"
    echo ""
    echo "🚀 Starting services..."
    
    # Start core services first
    echo "   Starting PostgreSQL and Redis..."
    docker-compose up -d postgres redis
    
    # Wait for core services
    echo "   Waiting for core services to be healthy..."
    sleep 10
    
    # Start Weaviate
    echo "   Starting Weaviate with OpenAI integration..."
    docker-compose up -d weaviate
    
    # Check Weaviate startup
    echo "   Checking Weaviate startup..."
    sleep 15
    
    if docker-compose ps weaviate | grep -q "Up"; then
        echo "✅ Weaviate started successfully!"
        
        # Start remaining services
        echo "   Starting remaining services..."
        docker-compose up -d
        
        echo ""
        echo "🎉 ReAgent deployment successful!"
        echo ""
        echo "📊 Service Status:"
        docker-compose ps
        
    else
        echo "❌ Weaviate failed to start. Check logs:"
        docker-compose logs weaviate
    fi
    
else
    echo ""
    echo "❌ Configuration validation failed. Please fix the issues above."
    echo "   Run './scripts/validate_env.sh' to check configuration."
fi

echo ""
echo "🔗 Useful Commands:"
echo "   - Check logs: docker-compose logs weaviate"
echo "   - Restart services: docker-compose restart"
echo "   - Stop all: docker-compose down"
echo "   - Validate config: ./scripts/validate_env.sh"