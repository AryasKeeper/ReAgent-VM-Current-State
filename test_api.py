#!/usr/bin/env python3
"""
Quick API test to verify system is working
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import redis
import psycopg2
import requests

app = FastAPI(title="ReAgent Recovery Test API")

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "message": "ReAgent system recovered"}

@app.get("/test-connections")
async def test_connections():
    """Test all external service connections"""
    results = {}
    
    # Test PostgreSQL
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,  
            database="reagent",
            user="reagent",
            password=os.getenv("POSTGRES_PASSWORD", "reagent_dev_password")
        )
        conn.close()
        results["postgres"] = "connected"
    except Exception as e:
        results["postgres"] = f"error: {str(e)}"
    
    # Test Redis
    try:
        r = redis.Redis(host="localhost", port=6379, db=0)
        r.ping()
        results["redis"] = "connected"
    except Exception as e:
        results["redis"] = f"error: {str(e)}"
    
    # Test Weaviate
    try:
        response = requests.get("http://localhost:8080/v1/.well-known/ready", timeout=5)
        if response.status_code == 200:
            results["weaviate"] = "connected"
        else:
            results["weaviate"] = f"status_code: {response.status_code}"
    except Exception as e:
        results["weaviate"] = f"error: {str(e)}"
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)