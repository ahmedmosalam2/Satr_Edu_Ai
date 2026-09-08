@echo off
title Satr Edu Launcher (Without Docker)
echo.
echo ===================================================
echo   Satr Edu - starting all services (No Docker)
echo ===================================================
echo.

:: 1. Start FastAPI AI Agent Backend
echo [1/4] Starting FastAPI Backend on port 8001...
start "Satr Edu - FastAPI (8001)" cmd /k "cd /d d:\Satr_Edu_Ai && python -m uvicorn main:app --reload --port 8001 --reload-exclude \"docker/data/*\""

:: 2. Start Celery Worker
echo [2/4] Starting Celery Worker...
start "Satr Edu - Celery Worker" cmd /k "cd /d d:\Satr_Edu_Ai && python -m celery -A src.tasks.process_tasks worker --loglevel=info"

:: 3. Start Django Main Backend
echo [3/4] Starting Django Main Backend on port 8000...
start "Satr Edu - Django Backend (8000)" cmd /k "cd /d c:\Users\Dell\Downloads\backend-grad && env\Scripts\python.exe manage.py runserver 127.0.0.1:8000"

:: 4. Start React Frontend
echo [4/4] Starting React Vite Frontend...
start "Satr Edu - React Frontend" cmd /k "cd /d c:\Users\Dell\Downloads\satr-edu && npm run dev"

echo.
echo ===================================================
echo ✅ All services launched! Opening web app...
echo ===================================================
echo.
timeout /t 5 /nobreak >nul
explorer "http://localhost:5173"
exit
