#!/bin/bash
set -e

# ---- Dynamic path resolution ----
# Always resolve relative to the directory this script lives in,
# regardless of where the user invokes it from.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# ---- ONNX Runtime library path (environment-agnostic) ----
# Look for onnxruntime dylibs relative to the project workspace.
# The workspace is assumed to be one level above this repo (agent_Phased/).
WORKSPACE_DIR="$(dirname "$DIR")"

# Search for onnxruntime lib directory dynamically
ONNX_LIB=""
if [ -d "$WORKSPACE_DIR/agentmem/deps" ]; then
    ONNX_LIB=$(find "$WORKSPACE_DIR/agentmem/deps" -name "lib" -type d 2>/dev/null | head -n 1)
fi

if [ -n "$ONNX_LIB" ]; then
    export DYLD_LIBRARY_PATH="$ONNX_LIB${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
    echo "ONNX Runtime library path: $ONNX_LIB"
else
    echo "Warning: onnxruntime lib directory not found. Semantic memory may not work."
fi

# ---- Activate virtual environment if present ----
if [ -f "$DIR/venv/bin/activate" ]; then
    source "$DIR/venv/bin/activate"
    echo "Activated virtualenv at $DIR/venv"
elif [ -n "$VIRTUAL_ENV" ]; then
    echo "Using existing virtualenv: $VIRTUAL_ENV"
else
    echo "Warning: No virtualenv found. Using system Python."
fi

# ---- Start the Python FastAPI backend ----
echo "Starting AgentPhased Backend..."
python "$DIR/agentphased/server.py" &
BACKEND_PID=$!

# ---- Start the Vite React frontend ----
echo "Starting AgentPhased Dashboard..."
cd "$DIR/dashboard"
npm run dev &
FRONTEND_PID=$!

# ---- Trap signals to kill background processes ----
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGINT SIGTERM EXIT

# ---- Wait for both processes ----
wait
