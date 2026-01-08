#!/usr/bin/env python3
"""
HTTP Server Wrapper for Financial Intelligence MCP

This server exposes the MCP tools via HTTP endpoints for frontend integration.
It wraps the existing server.py tools and provides REST API access.

Endpoints:
  POST /tools/check_client_suitability - Compliance check
  POST /tools/get_market_data - Market data retrieval
  GET /health - Health check

Usage:
  python http_server.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import asyncio
import json

# Import the MCP tool implementations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from mcp_tools import check_client_suitability_impl, get_market_data_impl

# Initialize FastAPI app
app = FastAPI(
    title="Financial Intelligence MCP HTTP Server",
    description="HTTP wrapper for MCP tools providing compliance-gated market data",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class TickerRequest(BaseModel):
    ticker: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="Financial Intelligence MCP",
        version="1.0.0"
    )


@app.post("/tools/check_client_suitability")
async def http_check_client_suitability(request: TickerRequest):
    """
    Compliance check endpoint

    Validates ticker against compliance rules and returns approval/denial status.
    """
    try:
        result_json = await check_client_suitability_impl(request.ticker)
        result = json.loads(result_json)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": str(e)
            }
        )


@app.post("/tools/get_market_data")
async def http_get_market_data(request: TickerRequest):
    """
    Market data retrieval endpoint

    Returns comprehensive market data for approved tickers.
    Note: This endpoint does NOT enforce compliance - that must be done separately
    via check_client_suitability.
    """
    try:
        result_json = await get_market_data_impl(request.ticker)
        result = json.loads(result_json)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": str(e)
            }
        )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Financial Intelligence MCP HTTP Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "compliance_check": "POST /tools/check_client_suitability",
            "market_data": "POST /tools/get_market_data"
        },
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


if __name__ == "__main__":
    print("=" * 80)
    print("Financial Intelligence MCP - HTTP Server")
    print("=" * 80)
    print()
    print("Server starting on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print()
    print("Endpoints:")
    print("  POST /tools/check_client_suitability")
    print("  POST /tools/get_market_data")
    print("  GET /health")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
