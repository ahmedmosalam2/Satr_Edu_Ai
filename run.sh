#!/bin/bash
# ══════════════════════════════════════════════════
# Local Development Runner (WSL / Linux)
# بيشغّل الـ FastAPI locally مع hot-reload
# يراقب src/ و main.py فقط — مش الـ data folders
# ══════════════════════════════════════════════════

# تأكد إن الـ packages اللازمة موجودة
if ! python -c "import pymongo" 2>/dev/null; then
    echo "⚠️  pymongo not installed — installing..."
    pip install pymongo
fi

echo "🚀 Starting Satr Edu AI (local dev)..."
echo "   Watching: src/, main.py"
echo "   Ignoring: docker/, data/, __pycache__"
echo ""

uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir src \
  --reload-dir . \
  --reload-include "*.py" \
  --reload-exclude "docker" \
  --reload-exclude "data" \
  --reload-exclude "qdrant_db" \
  --reload-exclude "__pycache__" \
  --reload-exclude "*.pyc" \
  --reload-exclude "*.wt" \
  --reload-exclude "*.lock"
