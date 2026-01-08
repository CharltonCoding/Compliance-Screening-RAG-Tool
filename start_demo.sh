#!/bin/bash

# =============================================================================
# Financial Intelligence MCP - Demo Startup Script
# =============================================================================
#
# This script starts both the Python MCP server and the Next.js frontend
# for testing the complete Financial Intelligence MCP system.
#
# Usage:
#   chmod +x start_demo.sh
#   ./start_demo.sh
#
# =============================================================================

set -e

echo "========================================================================"
echo "Financial Intelligence MCP - Starting Demo Environment"
echo "========================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating one...${NC}"
    python3.10 -m venv .venv
    source .venv/bin/activate
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    source .venv/bin/activate
    echo -e "${GREEN}✓${NC} Virtual environment activated"
fi

# Install Python dependencies if needed
echo ""
echo -e "${BLUE}Checking Python dependencies...${NC}"
if ! python -c "import fastmcp" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install -q -r requirements.txt 2>/dev/null || pip install fastmcp yfinance langgraph aiosqlite ragas datasets langchain-anthropic
    echo -e "${GREEN}✓${NC} Python dependencies installed"
else
    echo -e "${GREEN}✓${NC} Python dependencies already installed"
fi

# Check if Node modules are installed
echo ""
echo -e "${BLUE}Checking Node.js dependencies...${NC}"
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing Node.js dependencies (this may take a minute)..."
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓${NC} Node.js dependencies installed"
else
    echo -e "${GREEN}✓${NC} Node.js dependencies already installed"
fi

# Create results directory if it doesn't exist
mkdir -p results
mkdir -p logs

echo ""
echo "========================================================================"
echo "Starting Services"
echo "========================================================================"
echo ""

# Start Python HTTP server (wraps MCP tools) in background
echo -e "${BLUE}Starting Python HTTP Server on port 8000...${NC}"
python http_server.py > logs/mcp_server.log 2>&1 &
MCP_PID=$!
echo -e "${GREEN}✓${NC} HTTP Server started (PID: $MCP_PID)"
echo "   Logs: logs/mcp_server.log"

# Wait for MCP server to be ready
echo -e "${BLUE}Waiting for MCP server to be ready...${NC}"
sleep 3

# Check if MCP server is running
if ps -p $MCP_PID > /dev/null; then
    echo -e "${GREEN}✓${NC} MCP Server is running"
else
    echo -e "${YELLOW}⚠️  MCP Server may have failed to start. Check logs/mcp_server.log${NC}"
fi

# Start Next.js frontend in background
echo ""
echo -e "${BLUE}Starting Next.js Frontend on port 3000...${NC}"
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"
echo "   Logs: logs/frontend.log"

# Wait for frontend to compile
echo -e "${BLUE}Waiting for frontend to compile...${NC}"
sleep 5

echo ""
echo "========================================================================"
echo "✅ Demo Environment Ready!"
echo "========================================================================"
echo ""
echo -e "${GREEN}MCP Server:${NC}  http://localhost:8000 (PID: $MCP_PID)"
echo -e "${GREEN}Frontend:${NC}     http://localhost:3000 (PID: $FRONTEND_PID)"
echo ""
echo "To test the system:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Enter a ticker symbol (e.g., AAPL, MSFT, TSLA)"
echo "  3. Click 'Query' to see compliance check + market data"
echo ""
echo "To view logs:"
echo "  - MCP Server: tail -f logs/mcp_server.log"
echo "  - Frontend:   tail -f logs/frontend.log"
echo ""
echo "To stop all services:"
echo "  kill $MCP_PID $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop this script and shut down services..."
echo "========================================================================"
echo ""

# Save PIDs to file for cleanup
echo "$MCP_PID" > .demo_pids
echo "$FRONTEND_PID" >> .demo_pids

# Trap Ctrl+C to cleanup
cleanup() {
    echo ""
    echo "========================================================================"
    echo "Shutting down services..."
    echo "========================================================================"
    kill $MCP_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    rm -f .demo_pids
    echo "✓ Services stopped"
    exit 0
}

trap cleanup INT TERM

# Keep script running and show live logs
echo "Showing MCP Server logs (Ctrl+C to stop):"
echo "------------------------------------------------------------------------"
tail -f logs/mcp_server.log
