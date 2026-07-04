#!/bin/bash
set -e

# Start the Python FastAPI backend
echo "Starting AgentPhased Backend..."
source venv/bin/activate
export DYLD_LIBRARY_PATH=/Users/shekhawat/Desktop/agent_Phased/agentmem/deps/onnxruntime-osx-x86_64-1.17.3/lib/
python agentphased/server.py &
BACKEND_PID=$!

# Start the Vite React frontend
echo "Starting AgentPhased Dashboard..."
cd dashboard
npm run dev &
FRONTEND_PID=$!

# Trap SIGINT and SIGTERM to kill background processes
trap "kill $BACKEND_PID $FRONTEND_PID" SIGINT SIGTERM EXIT

# Wait for both processes
wait
