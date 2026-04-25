@echo off
echo.
echo ================================
echo    Satr Edu AI - Starting Up
echo ================================
echo.

:: 1. شغّل Docker (Redis + MongoDB)
echo [1/3] Starting Docker services (Redis + MongoDB)...
docker compose -f docker/docker-compose.yml up -d
echo.

:: 2. شغّل Celery Worker في تيرمنال منفصل
echo [2/3] Starting Celery Worker in a new window...
start "Celery Worker" cmd /k "celery -A src.tasks.process_tasks worker --loglevel=info"
echo.

:: انتظر ثانيتين عشان Celery يتجهّز
timeout /t 2 /nobreak >nul

:: 3. شغّل السيرفر
echo [3/3] Starting FastAPI Server...
echo.
echo ================================
echo  Server running at:
echo  http://localhost:8000
echo  http://localhost:8000/docs
echo ================================
echo.
uvicorn main:app --reload --reload-exclude "docker/data/*"
