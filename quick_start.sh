#!/bin/bash
# Quick Start Guide for E-Exam-Prepare

echo "=========================================="
echo "E-Exam-Prepare: Quick Start"
echo "=========================================="

# Step 1: Check Python
echo ""
echo "✓ Checking Python..."
python3 --version

# Step 2: Start Database & Cache
echo ""
echo "✓ Starting PostgreSQL & Redis (requires Docker)..."
docker-compose up -d
echo "  → PostgreSQL on localhost:5432"
echo "  → Redis on localhost:6379"
sleep 3

# Step 3: Start Backend
echo ""
echo "✓ Starting Backend Server..."
cd backend
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "  → Backend running on http://localhost:8000"
echo "  → OpenAPI docs: http://localhost:8000/docs"
cd ..
sleep 2

# Step 4: Start RAG Service
echo ""
echo "✓ Starting RAG Service..."
cd rag-service
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/rag.log 2>&1 &
RAG_PID=$!
echo "  → RAG Service running on http://localhost:8001"
cd ..
sleep 2

# Step 5: Start Frontend
echo ""
echo "✓ Starting Frontend..."
cd frontend
# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "  Installing dependencies (first run)..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
echo "  → Frontend running on http://localhost:3000"
cd ..

# Step 6: Show status
echo ""
echo "=========================================="
echo "✓ All services started!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  • Frontend:    http://localhost:3000"
echo "  • Backend:     http://localhost:8000"
echo "  • RAG Service: http://localhost:8001"
echo "  • Database:    localhost:5432"
echo "  • Cache:       localhost:6379"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Sign up with test account"
echo "  3. Explore the dashboard"
echo ""
echo "To stop all services:"
echo "  kill $BACKEND_PID $RAG_PID $FRONTEND_PID"
echo "  docker-compose down"
echo ""

# Keep script running
wait
